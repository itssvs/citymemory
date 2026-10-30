"""AI features built on the LLM client, each with a non-AI fallback and a cache.

- tag_complaint: picks a root cause from a FIXED list, with a short reason.
- asset_summary: writes a plain-language history of one asset from its records,
  and is rejected if it states a number that is not in those records.
- pattern_label: names a cluster of similar complaints.
"""
import hashlib
import json
import re

import llm
from causes import CAUSES, allowed_causes, tag_cause
from db import now, one

CAUSE_HELP = {
    "drainage": "water, blocked or overflowing drains, waterlogging or seepage damaging the asset",
    "utility_digging": "road cut or dug for cables, pipes or other utility work and not restored",
    "heavy_load": "damage from trucks, buses or heavy traffic",
    "poor_patch_material": "an earlier temporary patch that came off or failed quickly",
    "electrical_fault": "wiring, bulb, fuse or power problems (streetlights)",
    "wear_and_age": "old, worn, cracked or broken parts, general deterioration",
    "unknown": "not enough information",
}


def _key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def cache_get(conn, key):
    r = one(conn, "SELECT value FROM llm_cache WHERE key=?", (key,))
    return json.loads(r["value"]) if r else None


def cache_put(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO llm_cache (key,value,model,created_at) VALUES (?,?,?,?)",
                 (key, json.dumps(value), llm.MODEL, now().isoformat()))
    conn.commit()


# ---------------------------------------------------------------- cause tagging
def tag_complaint(conn, text: str, clean_text: str, category: str):
    """Return (cause, reason, source) where source is 'llm' or 'rules'."""
    key = _key("cause", llm.MODEL, text, category)
    allowed = allowed_causes(category)
    hit = cache_get(conn, key)
    if hit and hit["cause"] in allowed:
        return hit["cause"], hit["reason"], "llm"
    choices = "\n".join(f"- {c}: {CAUSE_HELP[c]}" for c in allowed)
    system = (
        "You classify civic infrastructure complaints for a municipal engineering team in India. "
        "Choose the single most likely ROOT CAUSE from the allowed list only. "
        'Reply with JSON only: {"cause": "<one allowed value>", "reason": "<max 15 words, quoting the complaint>"}'
    )
    user = f"Asset type: {category}\nAllowed causes:\n{choices}\n\nComplaint: \"{text}\""
    out = llm.chat(system, user, as_json=True, max_tokens=80)
    cause = (out or {}).get("cause", "").strip().lower().replace(" ", "_") if isinstance(out, dict) else ""
    if cause in allowed:
        reason = str(out.get("reason", "")).strip()[:160] or "model gave no reason"
        cache_put(conn, key, {"cause": cause, "reason": reason})
        return cause, reason, "llm"
    rc, rr = tag_cause(clean_text, category)
    return rc, rr, "rules"


# ---------------------------------------------------------------- asset summary
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set:
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(text or "")}


def _facts(asset, s):
    lasted = [r["lasted_days"] for r in s["durability"] if r["lasted_days"] is not None]
    inc = s["incidents"]
    return {
        "asset": f"{asset['name']} ({asset['asset_id']})",
        "type": asset["type"],
        "failures_total": s["incident_count"],
        "failures_last_12_months": s["incidents_12m"],
        "first_failure": inc[0]["start"][:7] if inc else None,
        "last_failure": inc[-1]["start"][:10] if inc else None,
        "citizen_complaints": s["complaint_count"],
        "temporary_repairs": s["cost"]["temporary_repairs"],
        "patch_spend_rupees": s["cost"]["patch_spend_total"],
        "patch_spend_last_12_months_rupees": s["cost"]["patch_spend_last_12m"],
        "replacement_cost_rupees": s["cost"]["replacement_cost"],
        "most_likely_cause": s["cause"]["primary"].replace("_", " "),
        "average_days_a_repair_lasted": round(sum(lasted) / len(lasted)) if lasted else None,
        "recommendation": {"replace": "plan a permanent fix instead of another patch",
                           "patch": "patching is still reasonable", "monitor": "monitor",
                           "fixed": "already fixed permanently; keep monitoring"}.get(s["cost"]["recommendation"], "monitor"),
        "priority_score_out_of_100": s["priority"]["score"],
        "recent_complaints": [c["text"] for c in s["complaints"][-4:]],
    }


def asset_summary(conn, asset, s):
    """Return {'text', 'source', 'model'}; falls back to the template summary."""
    facts = _facts(asset, s)
    key = _key("summary", llm.MODEL, facts)
    hit = cache_get(conn, key)
    if hit:
        return {"text": hit, "source": "llm", "model": llm.MODEL}
    system = (
        "You write short briefings for municipal engineers in India. Use ONLY the facts given. "
        "Write 3 or 4 plain sentences: what keeps failing and how often, what it has cost, the likely cause, "
        "and the recommended action. Copy numbers exactly as given; do not calculate, round or invent any number. "
        "Write rupee amounts as 'Rs' followed by the number. No headings, no bullet points."
    )
    text = llm.chat(system, json.dumps(facts, ensure_ascii=False), max_tokens=220)
    if text:
        allowed = _numbers(json.dumps(facts))
        invented = [n for n in _numbers(text) if n not in allowed]
        if not invented:
            cache_put(conn, key, text)
            return {"text": text, "source": "llm", "model": llm.MODEL}
        print(f"[ai] summary rejected, numbers not in records: {invented}")
    return {"text": s["summary"], "source": "template", "model": None}


# ---------------------------------------------------------------- pattern labels
def pattern_label(conn, examples: list, fallback: str):
    key = _key("pattern", llm.MODEL, examples)
    hit = cache_get(conn, key)
    if hit:
        return hit["label"], hit["description"], "llm"
    system = (
        "You name recurring civic problems for a municipal dashboard. Given similar citizen complaints, reply "
        'with JSON only: {"label": "<2 to 5 words>", "description": "<one sentence, max 20 words, no numbers>"}'
    )
    out = llm.chat(system, "\n".join(f"- {e}" for e in examples), as_json=True, max_tokens=90)
    if isinstance(out, dict) and out.get("label"):
        val = {"label": str(out["label"]).strip()[:60], "description": str(out.get("description", "")).strip()[:200]}
        cache_put(conn, key, val)
        return val["label"], val["description"], "llm"
    return fallback, "", "keywords"
