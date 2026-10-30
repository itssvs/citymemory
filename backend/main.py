"""CityMemory API.

Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import os
import shutil
import uuid
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ai
import auth
import security
import llm
import logic
import patterns
import workorders
from auth import ANY, CITIZEN, COMMISSIONER, ENGINEER, STAFF, require
from causes import severity_from_text
from db import DB_PATH, get_conn, init_db, now, one, rows
from textsim import SIM, normalise, to_blob

HERE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(HERE, "uploads")
DIST = os.path.join(HERE, "..", "frontend", "dist")
os.makedirs(UPLOADS, exist_ok=True)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    if not os.path.exists(DB_PATH):
        import seed

        seed.build()
    init_db()
    conn = get_conn()
    auth.seed_demo_users(conn)
    scrubbed = security.scrub_existing()
    if scrubbed:
        print(f"[startup] removed hidden metadata from {scrubbed} older photo(s)")
    n = logic.ensure_embeddings(conn)
    conn.close()
    print(f"[startup] matcher={SIM.backend} ({SIM.model_name}), embedded {n} complaints; "
          f"LLM {llm.MODEL} at {llm.BASE_URL}: {'ready' if llm.available(force=True) else 'not available'}")
    yield


app = FastAPI(title="CityMemory API", version="1.2", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DEMO_MODE = os.environ.get("CITYMEMORY_DEMO", "1") != "0"  # one-click demo logins; set CITYMEMORY_DEMO=0 for real use


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    for k, v in security.SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


@app.get("/api/photos/{name}", include_in_schema=False)
def photo(name: str, exp: int = 0, sig: str = ""):
    """Photos are only reachable through short-lived signed links handed to people allowed to see them."""
    if not security.check_photo_link(name, exp, sig):
        raise HTTPException(403, "This photo link is invalid or has expired. Reload the page.")
    path = os.path.join(UPLOADS, name)
    if not os.path.isfile(path):
        raise HTTPException(404, "photo not found")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})


def _asset_or_404(conn, asset_id):
    a = one(conn, "SELECT * FROM assets WHERE asset_id=?", (asset_id,))
    if not a:
        raise HTTPException(404, f"asset {asset_id} not found")
    return a


def _card(asset, s):
    return {
        **asset,
        "complaint_count": s["complaint_count"],
        "incident_count": s["incident_count"],
        "incidents_12m": s["incidents_12m"],
        "recurring": s["recurring"],
        "priority": s["priority"]["score"],
        "priority_summary": s["priority"]["summary"],
        "cause": s["cause"]["primary"],
        "recommendation": s["cost"]["recommendation"],
        "patch_spend_total": s["cost"]["patch_spend_total"],
        "replacement_cost": s["cost"]["replacement_cost"],
        "pending_review": s["pending_review"],
        "last_complaint": s["complaints"][-1]["created_at"] if s["complaints"] else None,
    }


# ---------------------------------------------------------------- read endpoints
@app.get("/api/health")
def health():
    conn = get_conn()
    updated = one(conn, "SELECT MAX(t) t FROM (SELECT MAX(created_at) t FROM complaints UNION ALL "
                        "SELECT MAX(completed_at) FROM repairs UNION ALL SELECT MAX(created_at) FROM work_orders)")["t"]
    conn.close()
    return {"ok": True, "demo": DEMO_MODE, "data_updated": updated, "similarity_backend": SIM.backend, "ai": {"embedder": SIM.info(), "llm": llm.info()}}


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    name: str


@app.post("/api/auth/login")
def login(body: LoginIn):
    wait = security.LIMITER.locked_for(body.username)
    if wait:
        raise HTTPException(429, f"Too many wrong attempts. Try again in {max(1, round(wait / 60))} minutes.")
    conn = get_conn()
    res = auth.login(conn, body.username, body.password)
    conn.close()
    if not res:
        security.LIMITER.failed(body.username)
        raise HTTPException(401, "Wrong username or password.")
    security.LIMITER.succeeded(body.username)
    token, user = res
    return {"token": token, "user": user}


class DemoIn(BaseModel):
    role: str


@app.post("/api/auth/demo")
def demo_login(body: DemoIn):
    """One-click login as a demo account. Only available while demo mode is on."""
    if not DEMO_MODE:
        raise HTTPException(404, "Demo access is turned off.")
    conn = get_conn()
    res = auth.demo_login(conn, body.role)
    conn.close()
    if not res:
        raise HTTPException(422, "role must be citizen, engineer or commissioner")
    token, user = res
    return {"token": token, "user": user}


@app.post("/api/auth/register")
def register(body: RegisterIn):
    """Citizens sign themselves up. Engineer and commissioner accounts are created by the city, not here."""
    import re

    username = body.username.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.]{3,30}", username):
        raise HTTPException(422, "Username: 3-30 letters, numbers, dots or underscores.")
    if len(body.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters.")
    conn = get_conn()
    if one(conn, "SELECT 1 FROM users WHERE username=?", (username,)):
        conn.close()
        raise HTTPException(409, "That username is taken.")
    auth.create_user(conn, username, body.password, "citizen", body.name.strip()[:60] or username)
    conn.commit()
    token, user = auth.login(conn, username, body.password)
    conn.close()
    return {"token": token, "user": user}


@app.get("/api/auth/me")
def me(user=Depends(ANY)):
    return {k: v for k, v in user.items() if k != "token"}


@app.post("/api/auth/logout")
def logout(user=Depends(ANY)):
    conn = get_conn()
    auth.logout(conn, user["token"])
    conn.close()
    return {"ok": True}


@app.get("/api/stats")
def stats(user=Depends(STAFF)):
    conn = get_conn()
    from datetime import timedelta

    states = [(a, logic.asset_state(conn, a)) for a in rows(conn, "SELECT * FROM assets")]
    cards = [_card(a, s) for a, s in states]
    # repairs old enough to judge: did they last 90 days before the asset failed again?
    cutoff = (now() - timedelta(days=90)).isoformat()
    judged = [r for _, s in states for r in s["durability"] if r["completed_at"] <= cutoff]
    held = [r for r in judged if r["lasted_days"] is None or r["lasted_days"] >= 90]
    lasted = [r["lasted_days"] for _, s in states for r in s["durability"] if r["lasted_days"] is not None]
    temp = one(conn, "SELECT COALESCE(SUM(cost),0) s, COUNT(*) n FROM repairs WHERE repair_type='temporary'")
    open_wos = workorders.list_orders(conn, "open")
    review = one(conn, "SELECT COUNT(*) n FROM complaints WHERE match_status='review'")["n"]
    linked = one(conn, "SELECT COUNT(*) n FROM complaints WHERE match_status IN ('auto','duplicate_linked')")["n"]
    conn.close()
    return {
        "assets": len(cards),
        "complaints": sum(c["complaint_count"] for c in cards),
        "recurring_assets": sum(1 for c in cards if c["recurring"]),
        "replace_recommended": sum(1 for c in cards if c["recommendation"] == "replace"),
        "patch_spend_total": round(temp["s"]),
        "temporary_repairs": temp["n"],
        "pending_review": review,
        "auto_linked": linked,
        "open_work_orders": len(open_wos),
        "overdue_work_orders": sum(1 for w in open_wos if w["overdue"]),
        "repairs_judged_90": len(judged),
        "repairs_held_90": len(held),
        "avg_days_lasted": round(sum(lasted) / len(lasted)) if lasted else None,
        "open_issues": sum(1 for _, s in states if any(p["name"] == "Open issue" and p["points"] > 0
                                                         for p in s["priority"]["components"])),
        "data_note": "Simulated demo data",
    }


def _all_cards(type=None):
    conn = get_conn()
    sql, args = "SELECT * FROM assets", ()
    if type:
        sql, args = sql + " WHERE type=?", (type,)
    jobs = {w["asset_id"]: w for w in workorders.list_orders(conn, "open")}
    out = []
    for a in rows(conn, sql, args):
        card = _card(a, logic.asset_state(conn, a))
        w = jobs.get(a["asset_id"])
        card["job"] = {"status": w["status"], "status_label": w["status_label"], "overdue": w["overdue"]} if w else None
        out.append(card)
    conn.close()
    return out


@app.get("/api/assets")
def list_assets(type: Optional[str] = None, user=Depends(STAFF)):
    return _all_cards(type)


@app.get("/api/public/assets")
def public_assets(user=Depends(ANY)):
    """What a citizen may see on the map: where known assets are and how often they were reported."""
    return [{"asset_id": c["asset_id"], "type": c["type"], "name": c["name"], "lat": c["lat"], "lng": c["lng"],
             "incident_count": c["incident_count"], "complaint_count": c["complaint_count"],
             "registered": c["registered"], "priority": 0} for c in _all_cards()]


@app.get("/api/priority")
def priority_list(limit: int = 20, user=Depends(STAFF)):
    cards = _all_cards()
    cards.sort(key=lambda c: c["priority"], reverse=True)
    return cards[:limit]


@app.get("/api/assets/{asset_id}")
def asset_detail(asset_id: str, user=Depends(STAFF)):
    conn = get_conn()
    a = _asset_or_404(conn, asset_id)
    s = logic.asset_state(conn, a)
    wo_open, wo_hist = workorders.open_for(conn, asset_id), workorders.history(conn, asset_id)
    conn.close()
    timeline = [security.sign_fields({"kind": "complaint", "date": c["created_at"], **c}, "photo_url") for c in s["complaints"]]
    timeline += [security.sign_fields({"kind": "repair", "date": r["completed_at"], **r}, "after_photo_url") for r in s["durability"]]
    wo_open = security.sign_fields(wo_open, "after_photo_url") if wo_open else None
    wo_hist = [security.sign_fields(w, "after_photo_url") for w in wo_hist]
    timeline.sort(key=lambda e: e["date"], reverse=True)
    return {
        "asset": a,
        "summary": s["summary"],
        "stats": {
            "complaints": s["complaint_count"],
            "incidents": s["incident_count"],
            "incidents_12m": s["incidents_12m"],
            "recurring": s["recurring"],
            "repairs": len(s["repairs"]),
            "pending_review": s["pending_review"],
        },
        "priority": s["priority"],
        "cause": s["cause"],
        "cost": s["cost"],
        "failure_window": s["window"],
        "incidents": s["incidents"],
        "timeline": timeline,
        "work_order": wo_open,
        "work_orders": wo_hist,
        "target_days": workorders.TARGET_DAYS.get(a["type"]),
    }


@app.get("/api/assets/{asset_id}/ai-summary")
def asset_ai_summary(asset_id: str, user=Depends(STAFF)):
    """LLM-written briefing from the asset's records; template text if the LLM is unavailable."""
    conn = get_conn()
    a = _asset_or_404(conn, asset_id)
    out = ai.asset_summary(conn, a, logic.asset_state(conn, a))
    conn.close()
    return out


@app.get("/api/patterns")
def get_patterns(user=Depends(STAFF)):
    conn = get_conn()
    out = patterns.find_patterns(conn, use_llm=True)
    conn.close()
    return out


@app.get("/api/search")
def search(q: str = Query(..., min_length=2), limit: int = 25, user=Depends(STAFF)):
    """Searchable history: matches asset ids/names and complaint/repair text, ranked by similarity."""
    conn = get_conn()
    qn = normalise(q)
    out = []
    for a in rows(conn, "SELECT * FROM assets WHERE asset_id LIKE ? OR name LIKE ?", (f"%{q}%", f"%{q}%")):
        out.append({"kind": "asset", "asset_id": a["asset_id"], "title": a["name"], "date": None, "score": 1.0})
    comps = rows(conn, "SELECT c.*, a.name FROM cv c JOIN assets a USING(asset_id)")
    if comps:
        sims = logic.TextQuery(q, qn).against(conn, comps)
        for c, sc in zip(comps, sims):
            if sc >= SEARCH_MIN.get(SIM.backend, 0.25):
                out.append({"kind": "complaint", "asset_id": c["asset_id"], "title": c["text"],
                            "subtitle": c["name"], "date": c["created_at"], "score": round(sc, 3)})
    for r in rows(conn, "SELECT r.*, a.name FROM repairs r JOIN assets a USING(asset_id) WHERE r.notes LIKE ? OR r.contractor LIKE ?",
                  (f"%{q}%", f"%{q}%")):
        out.append({"kind": "repair", "asset_id": r["asset_id"], "title": f"{r['repair_type']} repair: {r['notes']}",
                    "subtitle": f"{r['name']} · {r['contractor']}", "date": r["completed_at"], "score": 0.6})
    conn.close()
    out.sort(key=lambda x: (x["score"], x["date"] or ""), reverse=True)
    return out[:limit]


@app.get("/api/contractors")
def contractors(user=Depends(STAFF)):
    return _contractors()


def _contractors():
    """How long each contractor's repairs lasted before the asset failed again."""
    conn = get_conn()
    agg = {}
    for a in rows(conn, "SELECT * FROM assets"):
        s = logic.asset_state(conn, a)
        for r in s["durability"]:
            d = agg.setdefault(r["contractor"], {"contractor": r["contractor"], "repairs": 0, "failed_again": 0,
                                                  "lasted": [], "spend": 0.0})
            d["repairs"] += 1
            d["spend"] += r["cost"] or 0
            if r["lasted_days"] is not None:
                d["lasted"].append(r["lasted_days"])
                d["failed_again"] += 1
    conn.close()
    out = []
    for d in agg.values():
        lasted = d.pop("lasted")
        d["avg_days_lasted"] = round(sum(lasted) / len(lasted)) if lasted else None
        d["spend"] = round(d["spend"])
        out.append(d)
    out.sort(key=lambda d: (d["avg_days_lasted"] is None, d["avg_days_lasted"] or 0))
    return out


@app.get("/api/review")
def review_queue(user=Depends(ENGINEER)):
    conn = get_conn()
    out = rows(conn, "SELECT c.*, a.name AS asset_name FROM cv c JOIN assets a USING(asset_id) "
                     "WHERE c.match_status='review' OR a.registered=0 ORDER BY c.created_at DESC")
    conn.close()
    return [security.sign_fields(c, "photo_url") for c in out]


@app.get("/api/backtest")
def backtest(user=Depends(STAFF)):
    conn = get_conn()
    res = logic.backtest(conn)
    conn.close()
    return res


# ---------------------------------------------------------------- calendar
@app.get("/api/calendar")
def calendar(month: Optional[str] = None, user=Depends(ANY)):
    """Complaints filed and repairs done per day of one month (YYYY-MM).
    Staff see the whole ward; a citizen sees their own reports and repairs on the assets they reported."""
    import calendar as cal
    import re

    t = now()
    month = month or t.strftime("%Y-%m")
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(422, "month must look like 2026-10")
    y, m = int(month[:4]), int(month[5:])
    if not 1 <= m <= 12:
        raise HTTPException(422, "month must be 01-12")
    conn = get_conn()
    like = f"{month}-%"
    if user["role"] == "citizen":
        comps = rows(conn, "SELECT created_at FROM cv WHERE reporter=? AND created_at LIKE ?", (user["username"], like))
        reps = rows(conn, "SELECT completed_at FROM repairs WHERE completed_at LIKE ? AND asset_id IN "
                          "(SELECT asset_id FROM cv WHERE reporter=?)", (like, user["username"]))
    else:
        comps = rows(conn, "SELECT created_at FROM cv WHERE created_at LIKE ?", (like,))
        reps = rows(conn, "SELECT completed_at FROM repairs WHERE completed_at LIKE ?", (like,))
    conn.close()
    days = {d: {"day": d, "complaints": 0, "repairs": 0} for d in range(1, cal.monthrange(y, m)[1] + 1)}
    for c in comps:
        days[int(c["created_at"][8:10])]["complaints"] += 1
    for r in reps:
        days[int(r["completed_at"][8:10])]["repairs"] += 1
    return {
        "month": month,
        "first_weekday": cal.monthrange(y, m)[0],  # 0 = Monday
        "today": t.strftime("%Y-%m-%d"),
        "days": list(days.values()),
        "totals": {"complaints": len(comps), "repairs": len(reps)},
    }


# ---------------------------------------------------------------- citizen
def _citizen_status(c, asset_state):
    """Plain-language progress for one complaint, from the citizen's point of view."""
    created = c["created_at"]
    fix = next((r for r in asset_state["repairs"] if r["completed_at"] >= created), None)
    wo = asset_state.get("work_order")
    # each step has a stable key (for translation) plus an English label
    steps = [{"key": "submitted", "label": "Submitted", "done": True, "date": created}]
    in_review = c["match_status"] in ("review", "new_asset")
    steps.append({"key": "checking" if in_review else "linked",
                  "label": "Checked by an engineer" if in_review else "Linked to the asset's history", "done": not in_review})
    if fix:
        kind = "permanent fix" if fix["repair_type"] == "permanent" else "temporary repair"
        steps += [{"key": "assigned", "label": "Repair assigned", "done": True},
                  {"key": "started", "label": "Work started", "done": True},
                  {"key": "fixed", "kind": fix["repair_type"], "label": f"Fixed ({kind})", "done": True, "date": fix["completed_at"]}]
        return "Fixed", steps, fix.get("after_photo_url"), None
    steps += [{"key": "assigned", "contractor": wo["contractor"] if wo else None,
               "label": f"Repair assigned to {wo['contractor']}" if wo else "Repair assigned", "done": bool(wo),
               "date": wo["created_at"] if wo else None},
              {"key": "started", "label": "Work started", "done": bool(wo and wo["status"] == "in_progress"),
               "date": wo.get("started_at") if wo else None},
              {"key": "fixed", "label": "Fixed", "done": False}]
    if in_review:
        status = "Under review"
    elif wo:
        status = wo["status_label"]
    else:
        status = "Waiting for repair"
    target = wo["due_date"] if wo else None
    return status, steps, None, target


@app.get("/api/me/complaints")
def my_complaints(user=Depends(CITIZEN)):
    conn = get_conn()
    mine = rows(conn, "SELECT c.*, a.name AS asset_name, a.type AS asset_type FROM cv c JOIN assets a USING(asset_id) "
                      "WHERE c.reporter=? ORDER BY c.created_at DESC", (user["username"],))
    cache, out = {}, []
    for c in mine:
        if c["asset_id"] not in cache:
            a = one(conn, "SELECT * FROM assets WHERE asset_id=?", (c["asset_id"],))
            cache[c["asset_id"]] = {**logic.asset_state(conn, a), "work_order": workorders.open_for(conn, c["asset_id"])}
        s = cache[c["asset_id"]]
        status, steps, after_photo, target = _citizen_status(c, s)
        out.append({
            "id": c["id"], "text": c["text"], "category": c["category"], "created_at": c["created_at"],
            "photo_url": security.sign_photo(c["photo_url"]), "asset_id": c["asset_id"], "asset_name": c["asset_name"],
            "status": status, "steps": steps, "after_photo_url": security.sign_photo(after_photo), "target_date": target,
            "others_reported": max(0, s["complaint_count"] - 1),
            "times_failed": s["incident_count"],
        })
    conn.close()
    return out


# ---------------------------------------------------------------- commissioner
@app.get("/api/overview")
def overview(user=Depends(COMMISSIONER)):
    """Ward-level view for budget and accountability decisions."""
    from collections import defaultdict
    from datetime import timedelta

    conn = get_conn()
    t = now()
    year_ago = (t - timedelta(days=365)).isoformat()
    states = [(a, logic.asset_state(conn, a)) for a in rows(conn, "SELECT * FROM assets")]
    spend = defaultdict(lambda: {"temporary": 0.0, "permanent": 0.0})
    for r in rows(conn, "SELECT r.*, a.type FROM repairs r JOIN assets a USING(asset_id) WHERE completed_at>=?", (year_ago,)):
        spend[r["type"]][r["repair_type"]] += r["cost"] or 0
    months = defaultdict(int)
    for c in rows(conn, "SELECT created_at FROM cv WHERE created_at>=?", (year_ago,)):
        months[c["created_at"][:7]] += 1
    month_keys = []
    y, m = t.year, t.month
    for _ in range(12):
        month_keys.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    stop = []
    for a, s in states:
        if s["cost"]["recommendation"] == "replace":
            stop.append({"asset_id": a["asset_id"], "name": a["name"], "type": a["type"],
                         "incidents_12m": s["incidents_12m"], "cause": s["cause"]["primary"],
                         "patch_spend_total": s["cost"]["patch_spend_total"],
                         "patch_spend_last_12m": s["cost"]["patch_spend_last_12m"],
                         "replacement_cost": s["cost"]["replacement_cost"],
                         "years_to_break_even": s["cost"].get("years_to_break_even"),
                         "priority": s["priority"]["score"]})
    stop.sort(key=lambda x: x["priority"], reverse=True)
    lasted = [r["lasted_days"] for _, s in states for r in s["durability"] if r["lasted_days"] is not None]
    open_issues = sum(1 for _, s in states if any(p["name"] == "Open issue" and p["points"] > 0 for p in s["priority"]["components"]))
    conn.close()
    con = _contractors()
    rated = [c for c in con if c["avg_days_lasted"] is not None]
    return {
        "kpis": {
            "assets": len(states),
            "recurring_assets": sum(1 for _, s in states if s["recurring"]),
            "open_issues": open_issues,
            "complaints_12m": sum(months.values()),
            "patch_spend_12m": round(sum(v["temporary"] for v in spend.values())),
            "permanent_spend_12m": round(sum(v["permanent"] for v in spend.values())),
            "avg_days_repair_lasted": round(sum(lasted) / len(lasted)) if lasted else None,
        },
        "spend_by_type": [{"type": k, "temporary": round(v["temporary"]), "permanent": round(v["permanent"])}
                          for k, v in sorted(spend.items(), key=lambda kv: -(kv[1]["temporary"] + kv[1]["permanent"]))],
        "complaints_by_month": [{"month": k, "count": months.get(k, 0)} for k in reversed(month_keys)],
        "stop_patching": stop,
        "decision": {
            "assets": len(stop),
            "one_time_investment": round(sum(x["replacement_cost"] for x in stop)),
            "patch_spend_per_year_now": round(sum(x["patch_spend_last_12m"] for x in stop)),
        },
        "contractors": {"shortest": rated[0] if rated else None, "longest": rated[-1] if rated else None},
        "data_note": "Simulated demo data. Savings figures are illustrative.",
    }


# ---------------------------------------------------------------- write endpoints
SEARCH_MIN = {"sbert": 0.4, "hash": 0.3, "tfidf": 0.25}


def _tag_in_background(complaint_id: int):
    """LLM cause tagging runs after the citizen already has their reply (keyword rules if no LLM)."""
    conn = get_conn()
    c = one(conn, "SELECT * FROM cv WHERE id=?", (complaint_id,))
    if c:
        cause, reason, source = ai.tag_complaint(conn, c["text"], c["clean_text"], c["category"])
        conn.execute("UPDATE complaints SET cause=?, cause_reason=?, cause_source=? WHERE id=?",
                     (cause, reason, source, complaint_id))
        conn.commit()
    conn.close()


@app.post("/api/complaints")
def create_complaint(
    background: BackgroundTasks,
    text: str = Form(...),
    category: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    photo: Optional[UploadFile] = File(None),
    consent: bool = Form(False),
    user=Depends(require("citizen", "engineer")),
):
    """Pipeline: receive -> clean -> duplicate check -> locate & link -> store -> analyse (background)."""
    reporter = user["username"]
    if user["role"] == "citizen" and not consent:
        raise HTTPException(422, "Please confirm that you have read the privacy notice.")
    try:
        text, clean, category = logic.clean_complaint(text, category, lat, lng)
    except logic.CleanError as e:
        raise HTTPException(422, str(e))

    conn = get_conn()
    query = logic.TextQuery(text, clean)  # encode once; reused for duplicate check and matching
    dup = logic.find_duplicate(conn, reporter, category, lat, lng, query)
    if dup:
        a = one(conn, "SELECT * FROM assets WHERE asset_id=?", (dup["asset_id"],))
        s = logic.asset_state(conn, a)
        conn.close()
        return {"status": "duplicate", "message": "You already reported this issue recently; we kept your earlier report.",
                "complaint_id": dup["id"], "asset_id": a["asset_id"], "asset_name": a["name"],
                "history": _history_line(s)}

    best, candidates = logic.match_asset(conn, category, lat, lng, query)
    if best and best["score"] >= logic.AUTO_LINK:
        asset_id, status = best["asset_id"], "auto"
    elif best and best["score"] >= logic.REVIEW_FLOOR:
        asset_id, status = best["asset_id"], "review"
    else:
        asset_id, status = logic.next_asset_id(conn, category), "new_asset"
        conn.execute(
            "INSERT INTO assets (asset_id,type,name,ward,lat,lng,install_year,lifespan_years,replacement_cost,registered)"
            " VALUES (?,?,?,?,?,?,?,?,?,0)",
            (asset_id, category, f"Unregistered {category} near reported pin", "Demo Ward (simulated)", lat, lng, None, None, None),
        )

    try:
        photo_url = _save_photo(photo)
    except security.PhotoError as e:
        conn.close()
        raise HTTPException(422, str(e))

    cur = conn.execute(
        "INSERT INTO complaints (asset_id,text,clean_text,category,lat,lng,photo_url,created_at,reporter,severity,"
        "cause,cause_reason,match_score,match_status,embedding,embedding_model,consent_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (asset_id, text, clean, category, lat, lng, photo_url, now().isoformat(), reporter,
         severity_from_text(clean), None, None, best["score"] if best else None, status,
         to_blob(query.vec) if query.vec is not None else None, SIM.model_name if query.vec is not None else None,
         now().isoformat() if consent else None),
    )
    cid = cur.lastrowid
    conn.commit()
    a = one(conn, "SELECT * FROM assets WHERE asset_id=?", (asset_id,))
    s = logic.asset_state(conn, a)
    conn.close()
    background.add_task(_tag_in_background, cid)

    if status == "auto":
        msg = f"This spot is already known. {_history_line(s)} Your report has been added to its history."
    elif status == "review":
        msg = f"This looks like it may be a known issue. An engineer will confirm. {_history_line(s)}"
    else:
        msg = f"New issue registered as {asset_id}. An engineer will verify it."
    out = {"status": status, "message": msg, "complaint_id": cid, "asset_id": asset_id, "asset_name": a["name"],
           "match": best, "candidates": candidates, "history": _history_line(s), "matcher": SIM.backend}
    if user["role"] == "citizen":  # citizens get the outcome, not the internal scoring
        out.pop("candidates")
        out["match"] = None
    return out


def _save_photo(photo):
    """Validated, metadata-free copy of an uploaded image (see security.save_image)."""
    if photo is None or not photo.filename:
        return None
    return security.save_image(photo)


def _history_line(s):
    n = s["complaint_count"]
    reps = s["repairs"]
    line = f"Reported {n} time{'s' if n != 1 else ''}"
    if s["incident_count"] > 1:
        line += f" across {s['incident_count']} separate failures"
    line += "."
    if reps:
        last = max(reps, key=lambda r: r["completed_at"])
        line += f" Last repair: {logic.parse(last['completed_at']).strftime('%d %b %Y')} ({last['repair_type']})."
    return line


class ReviewDecision(BaseModel):
    action: str                      # "confirm" | "reassign" | "new_asset"
    asset_id: Optional[str] = None   # target for reassign
    asset_name: Optional[str] = None # name for new_asset


@app.post("/api/complaints/{complaint_id}/review")
def review_complaint(complaint_id: int, d: ReviewDecision, user=Depends(ENGINEER)):
    conn = get_conn()
    c = one(conn, "SELECT * FROM cv WHERE id=?", (complaint_id,))
    if not c:
        raise HTTPException(404, "complaint not found")
    if d.action == "confirm":
        conn.execute("UPDATE complaints SET match_status='confirmed' WHERE id=?", (complaint_id,))
        conn.execute("UPDATE assets SET registered=1 WHERE asset_id=?", (c["asset_id"],))
        target = c["asset_id"]
    elif d.action == "reassign":
        _asset_or_404(conn, d.asset_id)
        conn.execute("UPDATE complaints SET asset_id=?, match_status='confirmed' WHERE id=?", (d.asset_id, complaint_id))
        target = d.asset_id
    elif d.action == "new_asset":
        target = logic.next_asset_id(conn, c["category"])
        conn.execute(
            "INSERT INTO assets (asset_id,type,name,ward,lat,lng,registered) VALUES (?,?,?,?,?,?,1)",
            (target, c["category"], d.asset_name or f"New {c['category']}", "Demo Ward (simulated)", c["lat"], c["lng"]),
        )
        conn.execute("UPDATE complaints SET asset_id=?, match_status='confirmed' WHERE id=?", (target, complaint_id))
    else:
        raise HTTPException(422, "action must be confirm, reassign or new_asset")
    # drop an unregistered placeholder asset if nothing points at it any more
    old = c["asset_id"]
    if old != target and one(conn, "SELECT registered FROM assets WHERE asset_id=?", (old,))["registered"] == 0:
        if not one(conn, "SELECT id FROM complaints WHERE asset_id=? LIMIT 1", (old,)):
            conn.execute("DELETE FROM assets WHERE asset_id=?", (old,))
    conn.commit()
    conn.close()
    return {"ok": True, "asset_id": target}


class RepairIn(BaseModel):
    asset_id: str
    repair_type: str = "temporary"   # temporary | permanent
    cost: float
    contractor: str
    notes: Optional[str] = ""
    completed_at: Optional[str] = None


@app.post("/api/repairs")
def create_repair(r: RepairIn, user=Depends(ENGINEER)):
    if r.repair_type not in ("temporary", "permanent"):
        raise HTTPException(422, "repair_type must be temporary or permanent")
    if r.cost < 0:
        raise HTTPException(422, "cost must be positive")
    conn = get_conn()
    _asset_or_404(conn, r.asset_id)
    cur = conn.execute(
        "INSERT INTO repairs (asset_id,repair_type,cost,completed_at,contractor,notes) VALUES (?,?,?,?,?,?)",
        (r.asset_id, r.repair_type, r.cost, r.completed_at or now().isoformat(), r.contractor, r.notes),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "repair_id": cur.lastrowid}


class WorkOrderIn(BaseModel):
    contractor: str
    repair_type: str = "temporary"
    due_date: Optional[str] = None
    notes: Optional[str] = ""


def _wo_call(fn, *args):
    conn = get_conn()
    try:
        return fn(conn, *args)
    except workorders.WorkOrderError as e:
        raise HTTPException(422, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
    finally:
        conn.close()


@app.get("/api/work-orders")
def list_work_orders(status: str = "open", user=Depends(STAFF)):
    if status not in ("open", "completed", "all"):
        raise HTTPException(422, "status must be open, completed or all")
    return [security.sign_fields(w, "after_photo_url") for w in _wo_call(workorders.list_orders, status)]


@app.post("/api/assets/{asset_id}/work-orders")
def assign_work(asset_id: str, body: WorkOrderIn, user=Depends(ENGINEER)):
    conn = get_conn()
    a = _asset_or_404(conn, asset_id)
    conn.close()
    wo_id = _wo_call(workorders.assign, a, body.contractor, body.repair_type, body.due_date, body.notes, user["username"])
    return {"ok": True, "work_order_id": wo_id}


@app.post("/api/work-orders/{wo_id}/start")
def start_work(wo_id: int, user=Depends(ENGINEER)):
    _wo_call(workorders.start, wo_id)
    return {"ok": True}


@app.post("/api/work-orders/{wo_id}/complete")
def complete_work(wo_id: int, cost: float = Form(...), notes: Optional[str] = Form(""),
                  photo: Optional[UploadFile] = File(None), user=Depends(ENGINEER)):
    try:
        url = _save_photo(photo)
    except security.PhotoError as e:
        raise HTTPException(422, str(e))
    repair_id = _wo_call(workorders.complete, wo_id, cost, notes, url)
    return {"ok": True, "repair_id": repair_id}


@app.post("/api/reset")
def reset_demo(user=Depends(STAFF)):
    """Restore the simulated demo data (handy between rehearsals). Keeps the LLM cache."""
    import seed

    return {"ok": True, "seeded": seed.build(keep_cache=True)}


def _retag_all():
    conn = get_conn()
    for c in rows(conn, "SELECT id, text, clean_text, category FROM cv WHERE cause_source IS NOT 'llm'"):
        cause, reason, source = ai.tag_complaint(conn, c["text"], c["clean_text"], c["category"])
        conn.execute("UPDATE complaints SET cause=?, cause_reason=?, cause_source=? WHERE id=?",
                     (cause, reason, source, c["id"]))
        conn.commit()
    conn.close()


@app.post("/api/ai/retag")
def retag(background: BackgroundTasks, user=Depends(STAFF)):
    """Re-tag every complaint's cause with the LLM, in the background."""
    if not llm.available(force=True):
        raise HTTPException(503, f"LLM not available: {llm.info()['error']}")
    background.add_task(_retag_all)
    return {"ok": True, "message": "Re-tagging started in the background."}


# ---------------------------------------------------------------- serve built frontend
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="static")

    DIST_REAL = os.path.realpath(DIST)

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # only files inside the built frontend folder; '../' tricks fall through to the app page
        target = os.path.realpath(os.path.join(DIST_REAL, path))
        if path and target.startswith(DIST_REAL + os.sep) and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(DIST_REAL, "index.html"))
