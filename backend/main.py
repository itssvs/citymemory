"""CityMemory API.

Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import os
import shutil
import uuid
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ai
import llm
import logic
import patterns
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
    n = logic.ensure_embeddings(conn)
    conn.close()
    print(f"[startup] matcher={SIM.backend} ({SIM.model_name}), embedded {n} complaints; "
          f"LLM {llm.MODEL} at {llm.BASE_URL}: {'ready' if llm.available(force=True) else 'not available'}")
    yield


app = FastAPI(title="CityMemory API", version="1.1", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")


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
        "pending_review": s["pending_review"],
        "last_complaint": s["complaints"][-1]["created_at"] if s["complaints"] else None,
    }


# ---------------------------------------------------------------- read endpoints
@app.get("/api/health")
def health():
    return {"ok": True, "similarity_backend": SIM.backend, "ai": {"embedder": SIM.info(), "llm": llm.info()}}


@app.get("/api/stats")
def stats():
    conn = get_conn()
    cards = [_card(a, logic.asset_state(conn, a)) for a in rows(conn, "SELECT * FROM assets")]
    temp = one(conn, "SELECT COALESCE(SUM(cost),0) s, COUNT(*) n FROM repairs WHERE repair_type='temporary'")
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
        "data_note": "Simulated demo data",
    }


@app.get("/api/assets")
def list_assets(type: Optional[str] = None):
    conn = get_conn()
    sql, args = "SELECT * FROM assets", ()
    if type:
        sql, args = sql + " WHERE type=?", (type,)
    out = [_card(a, logic.asset_state(conn, a)) for a in rows(conn, sql, args)]
    conn.close()
    return out


@app.get("/api/priority")
def priority_list(limit: int = 20):
    cards = list_assets()
    cards.sort(key=lambda c: c["priority"], reverse=True)
    return cards[:limit]


@app.get("/api/assets/{asset_id}")
def asset_detail(asset_id: str):
    conn = get_conn()
    a = _asset_or_404(conn, asset_id)
    s = logic.asset_state(conn, a)
    conn.close()
    timeline = [{"kind": "complaint", "date": c["created_at"], **c} for c in s["complaints"]]
    timeline += [{"kind": "repair", "date": r["completed_at"], **r} for r in s["durability"]]
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
    }


@app.get("/api/assets/{asset_id}/ai-summary")
def asset_ai_summary(asset_id: str):
    """LLM-written briefing from the asset's records; template text if the LLM is unavailable."""
    conn = get_conn()
    a = _asset_or_404(conn, asset_id)
    out = ai.asset_summary(conn, a, logic.asset_state(conn, a))
    conn.close()
    return out


@app.get("/api/patterns")
def get_patterns():
    conn = get_conn()
    out = patterns.find_patterns(conn, use_llm=True)
    conn.close()
    return out


@app.get("/api/search")
def search(q: str = Query(..., min_length=2), limit: int = 25):
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
def contractors():
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
def review_queue():
    conn = get_conn()
    out = rows(conn, "SELECT c.*, a.name AS asset_name FROM cv c JOIN assets a USING(asset_id) "
                     "WHERE c.match_status='review' OR a.registered=0 ORDER BY c.created_at DESC")
    conn.close()
    return out


@app.get("/api/backtest")
def backtest():
    conn = get_conn()
    res = logic.backtest(conn)
    conn.close()
    return res


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
    reporter: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
):
    """Pipeline: receive -> clean -> duplicate check -> locate & link -> store -> analyse (background)."""
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

    photo_url = None
    if photo is not None and photo.filename:
        ext = os.path.splitext(photo.filename)[1].lower()[:5] or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(UPLOADS, fname), "wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_url = f"/uploads/{fname}"

    cur = conn.execute(
        "INSERT INTO complaints (asset_id,text,clean_text,category,lat,lng,photo_url,created_at,reporter,severity,"
        "cause,cause_reason,match_score,match_status,embedding,embedding_model) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (asset_id, text, clean, category, lat, lng, photo_url, now().isoformat(), reporter,
         severity_from_text(clean), None, None, best["score"] if best else None, status,
         to_blob(query.vec) if query.vec is not None else None, SIM.model_name if query.vec is not None else None),
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
    return {"status": status, "message": msg, "complaint_id": cid, "asset_id": asset_id, "asset_name": a["name"],
            "match": best, "candidates": candidates, "history": _history_line(s), "matcher": SIM.backend}


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
def review_complaint(complaint_id: int, d: ReviewDecision):
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
def create_repair(r: RepairIn):
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


@app.post("/api/reset")
def reset_demo():
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
def retag(background: BackgroundTasks):
    """Re-tag every complaint's cause with the LLM, in the background."""
    if not llm.available(force=True):
        raise HTTPException(503, f"LLM not available: {llm.info()['error']}")
    background.add_task(_retag_all)
    return {"ok": True, "message": "Re-tagging started in the background."}


# ---------------------------------------------------------------- serve built frontend
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="static")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = os.path.join(DIST, path)
        if path and os.path.isfile(target):
            return FileResponse(target)
        return FileResponse(os.path.join(DIST, "index.html"))
