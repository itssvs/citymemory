"""Run once before the demo so no AI answer has to be generated live.

    python ai_warmup.py            # embeddings + LLM cause tags + pattern labels + summaries
    python ai_warmup.py --check    # only report which AI parts are working

Everything the LLM produces is cached in the database and survives the dashboard's Reset button.
"""
import sys
import time

import ai
import llm
import logic
import patterns
from db import DB_PATH, get_conn, init_db, rows
from textsim import SIM


def check():
    print("Embeddings :", f"{SIM.backend} ({SIM.model_name})" + (f"  <- {SIM.error}" if SIM.error else ""))
    info = llm.info()
    print("LLM        :", f"{info['model']} at {info['host']}:", "READY" if info["available"] else f"NOT AVAILABLE ({info['error']})")
    if info["available"]:
        t = time.time()
        out = llm.chat("Reply with JSON only.", 'Return {"ok": true}', as_json=True, max_tokens=20)
        print("LLM test   :", out, f"in {time.time() - t:.1f}s")
    return info["available"]


def main():
    import os

    if not os.path.exists(DB_PATH):
        import seed

        seed.build()
    init_db()
    ok = check()
    if "--check" in sys.argv:
        return
    conn = get_conn()

    n = logic.ensure_embeddings(conn)
    print(f"\n[1/4] Embeddings ready ({SIM.model_name}); {n} newly encoded")

    if not ok:
        print("\nLLM not available, so cause tags, labels and summaries stay rule-based.")
        print("Start Ollama (or set LLM_BASE_URL / LLM_MODEL / LLM_API_KEY) and run this again.")
        return

    todo = rows(conn, "SELECT id, text, clean_text, category FROM cv WHERE cause_source IS NOT 'llm'")
    print(f"[2/4] Tagging causes for {len(todo)} complaints with {llm.MODEL} ...")
    t = time.time()
    changed = 0
    for i, c in enumerate(todo, 1):
        cause, reason, source = ai.tag_complaint(conn, c["text"], c["clean_text"], c["category"])
        conn.execute("UPDATE complaints SET cause=?, cause_reason=?, cause_source=? WHERE id=?",
                     (cause, reason, source, c["id"]))
        changed += source == "llm"
        if i % 10 == 0 or i == len(todo):
            conn.commit()
            print(f"      {i}/{len(todo)}  ({time.time() - t:.0f}s)")
    print(f"      {changed} tagged by the LLM, {len(todo) - changed} fell back to keyword rules")

    print("[3/4] Labelling ward-wide patterns ...")
    res = patterns.find_patterns(conn, use_llm=True)
    for p in res["patterns"]:
        print(f"      {p['label']!r} ({p['label_source']}): {p['size']} complaints, {len(p['assets'])} assets")

    print("[4/4] Writing asset summaries for the top 10 priority assets ...")
    states = [(a, logic.asset_state(conn, a)) for a in rows(conn, "SELECT * FROM assets")]
    states.sort(key=lambda x: x[1]["priority"]["score"], reverse=True)
    for a, s in states[:10]:
        out = ai.asset_summary(conn, a, s)
        print(f"      {a['asset_id']}: {out['source']}")
    conn.close()
    print("\nDone. Start the server: uvicorn main:app --port 8000")


if __name__ == "__main__":
    main()
