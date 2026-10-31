"""Ward-wide searchable timeline.

Every complaint, repair and repair job in the ward as one dated list, each tied to its asset.
Filters: date range, asset type, event kind, one asset. Search: by meaning for complaint text
(the same matcher used to link new complaints), plus asset ID, asset name, repair notes and contractor.
"""
from datetime import date, datetime, timedelta

import logic
import security
import workorders
from db import now, rows
from textsim import SIM, normalise

KINDS = ("complaint", "repair", "job")
TYPES = ("road", "drain", "streetlight", "footpath", "toilet")
SEARCH_MIN = {"sbert": 0.4, "hash": 0.3, "tfidf": 0.25}
MONTHS_SHOWN = 24


class TimelineError(ValueError):
    pass


def _day(s, name):
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise TimelineError(f"{name} must be a date like 2026-10-31.")


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _holding(days):
    return "Done today, holding so far" if days < 1 else f"Holding for {days} day{'' if days == 1 else 's'} so far"


def _all_events(conn):
    """Every event in the ward, with the links that make it a history rather than a list."""
    assets = {a["asset_id"]: a for a in rows(conn, "SELECT * FROM assets")}
    roles = {u["username"]: u["role"] for u in rows(conn, "SELECT username, role FROM users")}
    events = []
    for a in assets.values():
        s = logic.asset_state(conn, a)
        # which failure each complaint belongs to, and whether it opened that failure or repeated it
        where = {}
        for n, inc in enumerate(s["incidents"], 1):
            for k, cid in enumerate(inc["complaint_ids"]):
                where[cid] = (n, k == 0, inc["complaints"])
        base = {"asset_id": a["asset_id"], "asset_name": a["name"], "asset_type": a["type"]}
        for c in s["complaints"]:
            n, first, size = where.get(c["id"], (None, True, 1))
            link = (f"Started the {_ordinal(n)} failure of this asset" if first else f"Repeat report of the {_ordinal(n)} failure") if n else None
            events.append({**base, "id": f"c{c['id']}", "kind": "complaint", "date": c["created_at"],
                           "title": c["text"], "text": c["text"], "clean": c["clean_text"] or "", "cid": c["id"],
                           "photo_url": c["photo_url"], "cause": c["cause"], "severity": c["severity"],
                           "match_status": c["match_status"], "match_score": c["match_score"],
                           "failure_no": n, "opened_failure": first, "reports_in_failure": size, "link": link,
                           "source": "staff" if roles.get(c["reporter"]) in ("engineer", "commissioner") else "citizen"})
        for r in s["durability"]:
            held = (f"Held {r['lasted_days']} days, then failed again" if r["failed_again"]
                    else _holding((now() - logic.parse(r['completed_at'])).days))
            events.append({**base, "id": f"r{r['id']}", "kind": "repair", "date": r["completed_at"],
                           "title": f"{(r['repair_type'] or 'repair').capitalize()} repair by {r['contractor'] or 'unknown contractor'}",
                           "text": r["notes"] or "", "repair_type": r["repair_type"], "cost": r["cost"],
                           "contractor": r["contractor"], "lasted_days": r["lasted_days"], "failed_again": r["failed_again"],
                           "held": held, "after_photo_url": r.get("after_photo_url"), "work_order_id": r.get("work_order_id")})
    for w in rows(conn, "SELECT * FROM work_orders WHERE status != 'cancelled'"):
        a = assets.get(w["asset_id"])
        if not a:
            continue
        w = workorders.decorate(w)
        events.append({"asset_id": a["asset_id"], "asset_name": a["name"], "asset_type": a["type"],
                       "id": f"w{w['id']}", "kind": "job", "date": w["created_at"],
                       "title": f"{(w['repair_type'] or '').capitalize()} repair job assigned to {w['contractor']}",
                       "text": w["notes"] or "", "status": w["status"], "status_label": w["status_label"],
                       "contractor": w["contractor"], "due_date": w["due_date"], "overdue": w["overdue"],
                       "days_overdue": w["days_overdue"], "repair_type": w["repair_type"]})
    return events, assets


def _search(conn, events, assets, q):
    """Score each event against the query. Complaint text by meaning; everything else by words."""
    ql = q.strip().lower()
    hit_assets = {aid for aid, a in assets.items() if ql in aid.lower() or ql in a["name"].lower()}
    exact = {aid for aid in assets if aid.lower() == ql}
    if exact:  # an asset ID typed in full means "show me this asset's history", nothing fuzzy
        out = [e for e in events if e["asset_id"] in exact]
        for e in out:
            e["match"], e["match_on"] = 1.0, "asset"
        return out
    comps = [e for e in events if e["kind"] == "complaint"]
    sims = {}
    if comps:
        query = logic.TextQuery(q, normalise(q))
        rows_ = [{"id": e["cid"], "clean_text": e["clean"], "text": e["text"]} for e in comps]
        for e, sc in zip(comps, query.against(conn, rows_)):
            sims[e["id"]] = float(sc)
    cut = SEARCH_MIN.get(SIM.backend, 0.25)
    out = []
    for e in events:
        if e["asset_id"] in hit_assets:
            e["match"], e["match_on"] = 1.0, "asset"
        elif e["kind"] == "complaint" and sims.get(e["id"], 0) >= cut:
            e["match"], e["match_on"] = round(sims[e["id"]], 2), "meaning"
        elif ql in (e["text"] or "").lower() or ql in (e.get("contractor") or "").lower() or ql in e["title"].lower():
            e["match"], e["match_on"] = 0.9, "words"
        else:
            continue
        out.append(e)
    return out


def build(conn, start=None, end=None, types=None, kinds=None, asset_id=None, q=None, sort="date", offset=0, limit=40):
    d0, d1 = _day(start, "start"), _day(end, "end")
    if d0 and d1 and d0 > d1:
        raise TimelineError("The start date is after the end date.")
    types = [t for t in (types or "").split(",") if t] or list(TYPES)
    kinds = [k for k in (kinds or "").split(",") if k] or list(KINDS)
    bad = [x for x in types if x not in TYPES] + [x for x in kinds if x not in KINDS]
    if bad:
        raise TimelineError(f"Unknown filter value: {', '.join(bad)}.")
    if sort not in ("date", "match"):
        raise TimelineError("sort must be date or match.")

    events, assets = _all_events(conn)
    if asset_id and asset_id not in assets:
        raise TimelineError(f"No asset called {asset_id}.")
    events = [e for e in events if e["asset_type"] in types and (not asset_id or e["asset_id"] == asset_id)]
    if q and q.strip():
        events = _search(conn, events, assets, q)

    # month strip: everything that passes the non-date filters, so the chosen range can be seen in context
    this_month = now().date().replace(day=1)
    months = []
    m = this_month
    for _ in range(MONTHS_SHOWN):
        months.append(m.strftime("%Y-%m"))
        m = (m - timedelta(days=1)).replace(day=1)
    strip = {k: {"month": k, "complaint": 0, "repair": 0, "job": 0} for k in reversed(months)}
    for e in events:
        k = e["date"][:7]
        if k in strip:
            strip[k][e["kind"]] += 1

    def in_range(e):
        d = datetime.fromisoformat(e["date"]).date()
        return (not d0 or d >= d0) and (not d1 or d <= d1)

    ranged = [e for e in events if in_range(e)]
    counts = {k: sum(1 for e in ranged if e["kind"] == k) for k in KINDS}
    shown = [e for e in ranged if e["kind"] in kinds]
    if sort == "match" and q:
        shown.sort(key=lambda e: (e.get("match", 0), e["date"]), reverse=True)
    else:
        shown.sort(key=lambda e: e["date"], reverse=True)

    page = shown[offset:offset + limit]
    for e in page:
        e.pop("clean", None)
        e.pop("cid", None)
        security.sign_fields(e, "photo_url", "after_photo_url")
    spend = sum(e.get("cost") or 0 for e in ranged if e["kind"] == "repair" and "repair" in kinds)
    return {
        "events": page,
        "total": len(shown),
        "counts": counts,
        "assets_involved": len({e["asset_id"] for e in shown}),
        "repair_spend": round(spend),
        "months": list(strip.values()),
        "assets": sorted(({"asset_id": a["asset_id"], "name": a["name"], "type": a["type"]} for a in assets.values()),
                         key=lambda a: a["asset_id"]),
        "matcher": SIM.backend,
    }
