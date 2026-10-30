"""Generate SIMULATED demo data: assets, complaints and repairs.

Patterns are deliberate so the demo always shows something:
- ROAD-2045 fails every ~2-3 months because of a blocked drain; Contractor A keeps patching.
- Contractor B's repairs tend to last much longer than Contractor A's.
- Some assets are healthy, one had a permanent fix that held.

Run:  python seed.py      (wipes and recreates citymemory.db)
"""
import os
import random
from datetime import timedelta

import sqlite3

from causes import severity_from_text, tag_cause
from db import DB_PATH, get_conn, init_db, now
from textsim import normalise

random.seed(42)
BASE_LAT, BASE_LNG = 13.0318, 80.1807  # demo ward centre (approximate, Chennai)
WARD = "Demo Ward (simulated)"

TEXTS = {
    ("road", "drainage"): [
        "Big pothole again near the bus stop, water stagnant after rain",
        "pothole filled with water, bikes skidding, drain next to it is blocked",
        "Same spot broken again after rain, drain overflowing onto the road",
        "deep crater with stagnant water, road keeps breaking here",
        "road surface washed away near the drain, very dangerous at night",
        "water logging and pothole outside the stop, two wheeler fell yesterday",
    ],
    ("road", "poor_patch_material"): [
        "patch work came off within weeks, pothole is back",
        "loose gravel from last patch, road broken again at same spot",
        "pothole repaired last month already reopened",
    ],
    ("road", "utility_digging"): [
        "road dug up for cable work and not restored properly",
        "trench from pipeline work left open, uneven road",
    ],
    ("road", "heavy_load"): [
        "heavy trucks have made deep ruts on this stretch",
        "lorry traffic breaking the road near the godown",
    ],
    ("drain", "drainage"): [
        "drain blocked and overflowing onto the street, bad smell",
        "storm water drain clogged with garbage, water stagnant",
        "sewage overflow from the drain after rain",
        "drain choked again, water entering shops",
    ],
    ("streetlight", "electrical_fault"): [
        "street light not working for a week, very dark at night",
        "lamp post flickering every night",
        "street light not glowing, wire hanging from the pole",
        "light switched off again, area unsafe for women",
    ],
    ("footpath", "wear_and_age"): [
        "footpath tiles broken, elderly people tripping",
        "cracked slab on the footpath, drain cover missing",
        "footpath sinking and uneven near the school",
    ],
    ("toilet", "wear_and_age"): [
        "public toilet door broken and no water",
        "toilet tap broken, floor dirty, not usable",
    ],
}

REPAIR_NOTES = {
    "drainage": ["cold mix patch on pothole; drain not cleared", "pothole patched, water seepage from drain noted", "drain desilted"],
    "poor_patch_material": ["cold mix patch", "gravel filling"],
    "utility_digging": ["trench restored with patch"],
    "heavy_load": ["surface patch on ruts"],
    "electrical_fault": ["bulb replaced", "loose wire fixed"],
    "wear_and_age": ["broken tiles replaced", "door fixed"],
}

# (asset_id, type, name, dlat, dlng, install, lifespan, replacement_cost, cause,
#  n_incidents, mean_gap_days, contractor_mix, last_incident_open, permanent_fix_at_incident)
ASSETS = [
    ("ROAD-2045", "road", "Main Road, bus stop stretch", 0.0000, 0.0000, 2015, 10, 600000, "drainage", 9, 62, ["A"], True, None),
    ("ROAD-2046", "road", "Main Road, market junction", 0.0040, 0.0035, 2017, 10, 750000, "poor_patch_material", 6, 95, ["A", "A", "B"], True, None),
    ("ROAD-2047", "road", "School Street", -0.0035, 0.0050, 2019, 12, 400000, "utility_digging", 3, 150, ["B"], False, None),
    ("ROAD-2048", "road", "Godown Lane", 0.0070, -0.0040, 2016, 10, 500000, "heavy_load", 4, 120, ["C", "B"], False, None),
    ("ROAD-2049", "road", "Temple Street", -0.0060, -0.0030, 2020, 12, 350000, "poor_patch_material", 4, 110, ["A"], False, 3),
    ("ROAD-2050", "road", "Lake View Road", 0.0095, 0.0080, 2021, 12, 450000, "drainage", 2, 200, ["B"], False, None),
    ("DRAIN-1120", "drain", "Storm drain beside Main Road bus stop", 0.0004, 0.0003, 2012, 15, 300000, "drainage", 6, 85, ["C"], True, None),
    ("DRAIN-1121", "drain", "Market drain", 0.0045, 0.0030, 2014, 15, 280000, "drainage", 4, 120, ["C"], False, None),
    ("DRAIN-1122", "drain", "Canal Road drain", -0.0080, 0.0070, 2018, 15, 260000, "drainage", 2, 220, ["B"], False, None),
    ("LIGHT-778", "streetlight", "Light pole 12, Main Road", 0.0010, 0.0012, 2018, 8, 45000, "electrical_fault", 5, 90, ["D"], True, None),
    ("LIGHT-779", "streetlight", "Light pole 4, School Street", -0.0030, 0.0045, 2019, 8, 45000, "electrical_fault", 3, 140, ["D"], False, None),
    ("LIGHT-780", "streetlight", "Light pole 9, Park Road", 0.0060, 0.0090, 2020, 8, 45000, "electrical_fault", 1, 0, ["D"], False, None),
    ("LIGHT-781", "streetlight", "Light pole 2, Temple Street", -0.0058, -0.0026, 2017, 8, 45000, "electrical_fault", 4, 100, ["D"], False, None),
    ("PATH-310", "footpath", "Footpath outside Government School", -0.0033, 0.0055, 2014, 12, 220000, "wear_and_age", 3, 160, ["B"], False, None),
    ("PATH-311", "footpath", "Footpath, market junction", 0.0042, 0.0040, 2016, 12, 200000, "wear_and_age", 2, 210, ["C"], False, None),
    ("TOILET-55", "toilet", "Public toilet near bus stand", 0.0015, -0.0020, 2013, 15, 350000, "wear_and_age", 3, 170, ["C"], False, None),
    ("ROAD-2051", "road", "Park Road", 0.0065, 0.0095, 2022, 12, 420000, "unknown", 0, 0, ["B"], False, None),
    ("DRAIN-1123", "drain", "Temple tank inlet drain", -0.0065, -0.0045, 2015, 15, 250000, "drainage", 3, 150, ["C"], False, None),
]

CONTRACTORS = {"A": "Contractor A", "B": "Contractor B", "C": "Contractor C", "D": "Electrical Contractor D"}
# how long each contractor's temporary repairs tend to hold before the asset fails again
REPAIR_FACTOR = {"A": 0.35, "B": 0.85, "C": 0.6, "D": 0.6}
COST = {"road": (40000, 70000), "drain": (15000, 30000), "streetlight": (3000, 8000), "footpath": (20000, 40000), "toilet": (10000, 25000)}
REPORTERS = [f"citizen{i:03d}" for i in range(1, 80)]


def jitter(m=12):
    # roughly m metres of GPS noise
    return (random.uniform(-m, m) / 111000.0, random.uniform(-m, m) / 109000.0)


def _saved_cache():
    """LLM answers are slow to produce; keep them when the demo data is rebuilt."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        c = sqlite3.connect(DB_PATH)
        out = c.execute("SELECT key, value, model, created_at FROM llm_cache").fetchall()
        c.close()
        return out
    except sqlite3.Error:
        return []


def build(keep_cache=True):
    cache = _saved_cache() if keep_cache else []
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    conn = get_conn()
    if cache:
        conn.executemany("INSERT OR REPLACE INTO llm_cache VALUES (?,?,?,?)", cache)
    t_now = now()

    for (aid, typ, name, dlat, dlng, inst, life, repl, cause, n_inc, gap, mix, last_open, perm_at) in ASSETS:
        lat, lng = BASE_LAT + dlat, BASE_LNG + dlng
        conn.execute(
            "INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,1)",
            (aid, typ, name, WARD, lat, lng, inst, life, repl),
        )
        if n_inc == 0:
            continue
        # place incidents backwards from a recent date
        last_start = t_now - timedelta(days=random.randint(4, 12) if last_open else random.randint(40, 120))
        starts = [last_start]
        for _ in range(n_inc - 1):
            starts.append(starts[-1] - timedelta(days=max(25, int(random.gauss(gap, gap * 0.18)))))
        starts.reverse()
        texts = TEXTS.get((typ, cause)) or TEXTS[(typ, "drainage" if typ in ("road", "drain") else "wear_and_age")]

        for idx, st in enumerate(starts):
            for k in range(random.randint(1, 4) if aid in ("ROAD-2045", "DRAIN-1120") else random.randint(1, 3)):
                created = st + timedelta(days=random.randint(0, 6), hours=random.randint(7, 21))
                text = random.choice(texts)
                clean = normalise(text)
                c_tag, c_reason = tag_cause(clean, typ)
                jl, jg = jitter()
                conn.execute(
                    "INSERT INTO complaints (asset_id,text,clean_text,category,lat,lng,photo_url,created_at,reporter,"
                    "severity,cause,cause_reason,cause_source,match_score,match_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (aid, text, clean, typ, lat + jl, lng + jg, None, created.isoformat(), random.choice(REPORTERS),
                     severity_from_text(clean), c_tag, c_reason, "rules", None, "seeded"),
                )
            is_last = idx == len(starts) - 1
            if is_last and last_open:
                continue  # still unresolved
            contractor = mix[idx % len(mix)]
            done = st + timedelta(days=random.randint(5, 15))
            if perm_at is not None and idx == perm_at - 1:
                rtype, cost = "permanent", repl * random.uniform(0.85, 1.0)
                note = "full resurfacing with drainage correction"
            else:
                rtype = "temporary"
                cost = random.uniform(*COST[typ])
                note = random.choice(REPAIR_NOTES.get(cause, ["repair"]))
            if not is_last:  # nudge next incident so durability reflects the contractor
                nxt = starts[idx + 1]
                target = done + timedelta(days=max(10, int((nxt - done).days * (REPAIR_FACTOR[contractor] / 0.6))))
                ceiling = starts[idx + 2] - timedelta(days=20) if idx + 2 < len(starts) else t_now - timedelta(days=3)
                starts[idx + 1] = max(min(target, ceiling), done + timedelta(days=10))
            conn.execute(
                "INSERT INTO repairs (asset_id,repair_type,cost,completed_at,contractor,notes) VALUES (?,?,?,?,?,?)",
                (aid, rtype, round(cost, -2), done.isoformat(), CONTRACTORS[contractor], note),
            )
    conn.commit()
    _apply_cached_ai(conn)
    import logic

    logic.ensure_embeddings(conn)
    n = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("assets", "complaints", "repairs")}
    conn.close()
    return n


def _apply_cached_ai(conn):
    """Reuse cause tags the LLM already produced for the same text (no LLM call here)."""
    import ai

    for cid, text, clean, cat in conn.execute("SELECT id, text, clean_text, category FROM complaints").fetchall():
        hit = ai.cache_get(conn, ai._key("cause", ai.llm.MODEL, text, cat))
        if hit:
            conn.execute("UPDATE complaints SET cause=?, cause_reason=?, cause_source='llm' WHERE id=?",
                         (hit["cause"], hit["reason"], cid))
    conn.commit()


if __name__ == "__main__":
    print("Seeded (simulated):", build())
