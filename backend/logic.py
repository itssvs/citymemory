"""CityMemory core logic: clean -> locate -> link -> analyse.

Everything here is deliberately simple and explainable: distance maths, text similarity,
time-gap grouping and a transparent priority formula.
"""
import math
import statistics
from collections import Counter
from datetime import datetime, timedelta

from causes import tag_cause
from db import now, one, rows
import numpy as np

from textsim import SIM, from_blob, normalise, to_blob

# ---- tunable settings -------------------------------------------------------------
MATCH_RADIUS_M = 60          # how far from the pin we look for candidate assets
AUTO_LINK = 0.62             # combined score at or above this links automatically
REVIEW_FLOOR = 0.38          # between REVIEW_FLOOR and AUTO_LINK an engineer confirms
W_DISTANCE, W_TEXT = 0.6, 0.4
INCIDENT_GAP_DAYS = 14       # complaints closer than this belong to one failure incident
RECURRING_INCIDENTS = 3      # incidents in the last 12 months to flag "recurring"
DUPLICATE_DAYS = 7
MIN_TEXT_CHARS = 10
DUPLICATE_SIM = {"sbert": 0.75, "hash": 0.6, "tfidf": 0.5}

CATEGORIES = {"road", "drain", "streetlight", "footpath", "toilet"}
PREFIX = {"road": "ROAD", "drain": "DRAIN", "streetlight": "LIGHT", "footpath": "PATH", "toilet": "TOILET"}


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---- 1. clean ---------------------------------------------------------------------
class CleanError(ValueError):
    pass


def clean_complaint(text: str, category: str, lat, lng):
    text = (text or "").strip()
    category = (category or "").strip().lower()
    if category not in CATEGORIES:
        raise CleanError(f"category must be one of {sorted(CATEGORIES)}")
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise CleanError("a valid map location is required")
    if len(text) < MIN_TEXT_CHARS:
        raise CleanError(f"please describe the issue in at least {MIN_TEXT_CHARS} characters")
    return " ".join(text.split()), normalise(text), category


# ---- embeddings ---------------------------------------------------------------------
def ensure_embeddings(conn, batch=64) -> int:
    """Encode every complaint that has no vector for the current model. Returns how many."""
    if not SIM.is_vector:
        return 0
    todo = rows(conn, "SELECT id, text FROM complaints WHERE embedding IS NULL OR embedding_model IS NOT ?",
                (SIM.model_name,))
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        vecs = SIM.encode([c["text"] for c in chunk])
        conn.executemany("UPDATE complaints SET embedding=?, embedding_model=? WHERE id=?",
                         [(to_blob(v), SIM.model_name, c["id"]) for c, v in zip(chunk, vecs)])
    conn.commit()
    return len(todo)


def stored_vectors(conn, where="", args=()):
    """(complaint rows, matrix) for complaints with a vector from the current model."""
    rs = rows(conn, f"SELECT id, asset_id, text, clean_text, category, created_at, embedding FROM complaints "
                    f"WHERE embedding_model IS ? {where}", (SIM.model_name, *args))
    if not rs:
        return [], None
    mat = np.vstack([from_blob(r.pop("embedding")) for r in rs])
    return rs, mat


class TextQuery:
    """One incoming complaint text, encoded once and compared against history."""

    def __init__(self, raw, clean):
        self.raw, self.clean = raw, clean
        self.vec = SIM.encode([raw])[0] if SIM.is_vector else None

    def against(self, conn, history_rows, corpus=None):
        """Similarity to each complaint row (needs 'id' and 'clean_text')."""
        if not history_rows:
            return []
        if self.vec is not None:
            ids = [h["id"] for h in history_rows]
            marks = ",".join("?" * len(ids))
            got = {r["id"]: from_blob(r["embedding"]) for r in rows(
                conn, f"SELECT id, embedding FROM complaints WHERE id IN ({marks}) AND embedding_model IS ?",
                (*ids, SIM.model_name))}
            missing = [h for h in history_rows if h["id"] not in got]
            if missing:  # encode on the fly (e.g. model switched) and keep it
                for h, v in zip(missing, SIM.encode([h.get("text") or h["clean_text"] for h in missing])):
                    got[h["id"]] = v
            return SIM.cosine(self.vec, np.vstack([got[h["id"]] for h in history_rows]))
        return SIM.tfidf_scores(self.clean, [h["clean_text"] or "" for h in history_rows], corpus)


def find_duplicate(conn, reporter, category, lat, lng, query):
    """Same reporter, same kind of issue, same spot, within a few days -> duplicate."""
    if not reporter:
        return None
    since = (now() - timedelta(days=DUPLICATE_DAYS)).isoformat()
    recent = [c for c in rows(conn, "SELECT * FROM cv WHERE reporter=? AND category=? AND created_at>=?",
                              (reporter, category, since))
              if c["lat"] is not None and haversine_m(lat, lng, c["lat"], c["lng"]) <= 30]
    for c, sc in zip(recent, query.against(conn, recent)):
        if sc >= DUPLICATE_SIM.get(SIM.backend, 0.5):
            return c
    return None


# ---- 2/3. locate and link -------------------------------------------------------------
def match_asset(conn, category, lat, lng, query):
    """Return (best_candidate_or_None, candidates). Each candidate carries its scores."""
    nearby = []
    for a in rows(conn, "SELECT * FROM assets WHERE type=?", (category,)):
        d = haversine_m(lat, lng, a["lat"], a["lng"])
        if d <= MATCH_RADIUS_M:
            nearby.append((a, d))
    if not nearby:
        return None, []

    corpus = None if SIM.is_vector else [r["clean_text"] or "" for r in rows(conn, "SELECT clean_text FROM cv LIMIT 500")]
    candidates = []
    for a, d in nearby:
        history = rows(conn, "SELECT id, text, clean_text FROM cv WHERE asset_id=? ORDER BY created_at DESC LIMIT 25",
                       (a["asset_id"],))
        sims = query.against(conn, history, corpus)
        text_score = max(sims) if sims else 0.0
        dist_score = max(0.0, 1.0 - d / MATCH_RADIUS_M)
        combined = W_DISTANCE * dist_score + W_TEXT * text_score
        candidates.append({
            "asset_id": a["asset_id"], "name": a["name"], "distance_m": round(d, 1),
            "distance_score": round(dist_score, 3), "text_score": round(text_score, 3),
            "score": round(combined, 3), "matcher": SIM.backend,
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0], candidates


def next_asset_id(conn, category):
    prefix = PREFIX[category]
    ids = [r["asset_id"] for r in rows(conn, "SELECT asset_id FROM assets WHERE asset_id LIKE ?", (prefix + "-%",))]
    nums = [int(i.split("-")[1]) for i in ids if i.split("-")[1].isdigit()]
    return f"{prefix}-{(max(nums) + 1) if nums else 1001}"


# ---- 4. analyse -------------------------------------------------------------------
def incidents_for(complaints):
    """Group complaints (any order) into failure incidents by time gap."""
    cs = sorted(complaints, key=lambda c: c["created_at"])
    groups = []
    for c in cs:
        t = parse(c["created_at"])
        if groups and (t - groups[-1]["end"]).days <= INCIDENT_GAP_DAYS:
            groups[-1]["end"] = t
            groups[-1]["complaint_ids"].append(c["id"])
        else:
            groups.append({"start": t, "end": t, "complaint_ids": [c["id"]]})
    return [
        {
            "start": g["start"].isoformat(),
            "end": g["end"].isoformat(),
            "complaints": len(g["complaint_ids"]),
            "complaint_ids": g["complaint_ids"],
        }
        for g in groups
    ]


def failure_window(incidents):
    """Estimate the next failure from the gaps between past incidents, as a range."""
    if len(incidents) < 3:
        return {"available": False, "reason": "needs at least 3 past incidents"}
    starts = [parse(i["start"]) for i in incidents]
    gaps = [(b - a).days for a, b in zip(starts, starts[1:])]
    mean = statistics.mean(gaps)
    spread = statistics.pstdev(gaps) if len(gaps) > 1 else mean * 0.3
    spread = max(spread, 7)
    last = starts[-1]
    lo = last + timedelta(days=max(1, mean - spread))
    hi = last + timedelta(days=mean + spread)
    return {
        "available": True,
        "mean_gap_days": round(mean),
        "earliest": lo.date().isoformat(),
        "latest": hi.date().isoformat(),
        "based_on_gaps": len(gaps),
        "note": "Estimate from the average gap between past failures; a range, not a forecast.",
    }


def repair_durability(repairs, incidents):
    """Days each repair lasted until the next incident started (None = still holding)."""
    starts = sorted(parse(i["start"]) for i in incidents)
    out = []
    for r in sorted(repairs, key=lambda r: r["completed_at"]):
        done = parse(r["completed_at"])
        nxt = next((s for s in starts if s > done), None)
        out.append({**r, "lasted_days": (nxt - done).days if nxt else None, "failed_again": nxt is not None})
    return out


BREAK_EVEN_YEARS = 4         # replace if a permanent fix pays back within this many years of avoided patching


def cost_comparison(asset, repairs, incidents_12m=0, incidents=None):
    temp = [r for r in repairs if r["repair_type"] == "temporary"]
    spent_total = sum(r["cost"] or 0 for r in temp)
    cutoff = now() - timedelta(days=365)
    spent_12m = sum(r["cost"] or 0 for r in temp if parse(r["completed_at"]) >= cutoff)
    replacement = asset.get("replacement_cost") or 0
    out = {
        "temporary_repairs": len(temp),
        "patch_spend_total": round(spent_total),
        "patch_spend_last_12m": round(spent_12m),
        "projected_patch_spend_next_12m": round(spent_12m),
        "replacement_cost": round(replacement),
        "recommendation": "monitor",
        "message": "Not enough repair history to compare.",
    }
    # a permanent fix with no failure since then: the decision has been made, now monitor it
    perm = [r for r in repairs if r["repair_type"] == "permanent"]
    if perm:
        last = max(perm, key=lambda r: r["completed_at"])
        failed_since = any(parse(i["start"]) > parse(last["completed_at"]) for i in (incidents or []))
        if not failed_since:
            out["recommendation"] = "fixed"
            out["fixed_on"] = last["completed_at"]
            out["message"] = (
                f"Fixed permanently on {parse(last['completed_at']).strftime('%d %b %Y')} by {last['contractor']} "
                f"for ₹{(last['cost'] or 0):,.0f}. No failures since. Keep monitoring."
            )
            return out
    if replacement and spent_12m:
        out["years_to_break_even"] = round(replacement / spent_12m, 1)
        if spent_total >= replacement or (incidents_12m >= 3 and out["years_to_break_even"] <= BREAK_EVEN_YEARS):
            out["recommendation"] = "replace"
            out["message"] = (
                f"Patching has cost ₹{spent_total:,.0f} so far (₹{spent_12m:,.0f} in the last 12 months). "
                f"A permanent fix costs about ₹{replacement:,.0f} and would pay back in about "
                f"{out['years_to_break_even']} years at the current patch rate. Stop patching."
            )
        else:
            out["recommendation"] = "patch"
            out["message"] = (
                f"Patch spend in the last 12 months (₹{spent_12m:,.0f}) is still well below the "
                f"replacement cost (₹{replacement:,.0f}). Patching remains reasonable for now."
            )
    return out


def cause_summary(complaints, repairs, category):
    sources = Counter(c.get("cause_source") or "pending" for c in complaints)
    counts = Counter(c["cause"] for c in complaints if c.get("cause") and c["cause"] != "unknown")
    for r in repairs:
        cause, _ = tag_cause(normalise(r.get("notes") or ""), category)
        if cause != "unknown":
            counts[cause] += 1
    if not counts:
        return {"primary": "unknown", "counts": {}, "sources": dict(sources)}
    return {"primary": counts.most_common(1)[0][0], "counts": dict(counts.most_common()), "sources": dict(sources)}


def priority(asset, complaints, repairs, incidents):
    """Transparent 0-100 score. Every component is returned with a plain reason."""
    t = now()
    year_ago = t - timedelta(days=365)
    inc_12m = [i for i in incidents if parse(i["start"]) >= year_ago]
    last_c = max((parse(c["created_at"]) for c in complaints), default=None)
    sev = [c["severity"] for c in complaints if c.get("severity")]
    avg_sev = statistics.mean(sev) if sev else 0
    spend_12m = sum(r["cost"] or 0 for r in repairs if parse(r["completed_at"]) >= year_ago)
    replacement = asset.get("replacement_cost") or 1
    last_fix = max((parse(r["completed_at"]) for r in repairs), default=None)
    open_since = None
    if last_c and (last_fix is None or last_c > last_fix):
        after = [parse(c["created_at"]) for c in complaints if last_fix is None or parse(c["created_at"]) > last_fix]
        open_since = min(after)
    days_open = (t - open_since).days if open_since else 0
    days_since_last = (t - last_c).days if last_c else None

    parts = [
        ("Repeat failures", min(len(inc_12m) / 6, 1) * 35, f"{len(inc_12m)} failure incidents in the last 12 months"),
        (
            "Recency",
            (max(0.0, 1 - days_since_last / 90) * 15) if days_since_last is not None else 0,
            f"last complaint {days_since_last} days ago" if days_since_last is not None else "no complaints",
        ),
        ("Severity", avg_sev / 5 * 15, f"average reported severity {avg_sev:.1f} of 5"),
        ("Spend", min(spend_12m / replacement, 1) * 20, f"₹{spend_12m:,.0f} spent in 12 months ({spend_12m / replacement:.0%} of replacement cost)"),
        (
            "Open issue",
            min(days_open / 30, 1) * 15,
            f"unresolved for {days_open} days since the last fix" if open_since else "no open issue",
        ),
    ]
    score = round(sum(p[1] for p in parts))
    return {
        "score": score,
        "components": [{"name": n, "points": round(p, 1), "reason": r} for n, p, r in parts],
        "summary": "; ".join(r for n, p, r in parts if p >= 5) or "low activity",
    }


def asset_summary(asset, s):
    """Plain-language one-paragraph summary an official can paste into a report."""
    inc = s["incidents"]
    rep = s["repairs"]
    if not inc:
        return f"{asset['name']} ({asset['asset_id']}) has no recorded failures."
    first = parse(inc[0]["start"]).strftime("%b %Y")
    temp = sum(1 for r in rep if r["repair_type"] == "temporary")
    cause = s["cause"]["primary"].replace("_", " ")
    text = (
        f"{asset['name']} ({asset['asset_id']}) has failed {len(inc)} times since {first}, "
        f"with {s['complaint_count']} citizen complaints and {temp} temporary repairs costing "
        f"₹{s['cost']['patch_spend_total']:,.0f}."
    )
    if cause != "unknown":
        text += f" The most likely recurring cause is {cause}."
    lasted = [r["lasted_days"] for r in s["durability"] if r["lasted_days"] is not None]
    if lasted:
        text += f" Repairs have lasted {round(statistics.mean(lasted))} days on average before the next failure."
    if s["cost"]["recommendation"] == "replace":
        text += " Recommendation: plan a permanent fix instead of another patch."
    return text


def asset_state(conn, asset):
    """All derived facts for one asset."""
    complaints = rows(conn, "SELECT * FROM cv WHERE asset_id=? ORDER BY created_at", (asset["asset_id"],))
    repairs = rows(conn, "SELECT * FROM repairs WHERE asset_id=? ORDER BY completed_at", (asset["asset_id"],))
    incidents = incidents_for(complaints)
    year_ago = now() - timedelta(days=365)
    inc_12m = [i for i in incidents if parse(i["start"]) >= year_ago]
    s = {
        "complaints": complaints,
        "repairs": repairs,
        "incidents": incidents,
        "complaint_count": len(complaints),
        "incident_count": len(incidents),
        "incidents_12m": len(inc_12m),
        "recurring": len(inc_12m) >= RECURRING_INCIDENTS,
        "cause": cause_summary(complaints, repairs, asset["type"]),
        "cost": cost_comparison(asset, repairs, len(inc_12m), incidents),
        "durability": repair_durability(repairs, incidents),
        "window": failure_window(incidents),
        "priority": priority(asset, complaints, repairs, incidents),
        "pending_review": sum(1 for c in complaints if c.get("match_status") == "review"),
    }
    s["summary"] = asset_summary(asset, s)
    return s


def backtest(conn):
    """Hide each asset's last incident, predict it from earlier gaps, check if it fell inside the window."""
    results = []
    for a in rows(conn, "SELECT * FROM assets"):
        cs = rows(conn, "SELECT id, created_at FROM complaints WHERE asset_id=?", (a["asset_id"],))
        inc = incidents_for(cs)
        if len(inc) < 4:
            continue
        w = failure_window(inc[:-1])
        actual = parse(inc[-1]["start"]).date()
        lo, hi = datetime.fromisoformat(w["earliest"]).date(), datetime.fromisoformat(w["latest"]).date()
        err = 0 if lo <= actual <= hi else min(abs((actual - lo).days), abs((actual - hi).days))
        results.append(
            {
                "asset_id": a["asset_id"],
                "name": a["name"],
                "window": [w["earliest"], w["latest"]],
                "actual": actual.isoformat(),
                "hit": lo <= actual <= hi,
                "days_outside": err,
            }
        )
    hits = sum(1 for r in results if r["hit"])
    return {
        "tested_assets": len(results),
        "inside_window": hits,
        "hit_rate": round(hits / len(results), 2) if results else None,
        "median_days_outside_when_missed": (
            statistics.median([r["days_outside"] for r in results if not r["hit"]]) if hits < len(results) else 0
        ),
        "results": results,
        "note": "Run on simulated data; shows the method, not real-world accuracy.",
    }
