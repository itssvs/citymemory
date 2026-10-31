"""Show the jury exactly what was stored for the latest complaint (or a given reference number).

Run from the backend folder:
    python show_record.py          # latest complaint
    python show_record.py 132      # complaint #132
"""
import os
import sqlite3
import sys

import numpy as np

from db import DB_PATH

HERE = os.path.dirname(os.path.abspath(__file__))
LINE = "-" * 64


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if len(sys.argv) > 1:
        c = conn.execute("SELECT * FROM complaints WHERE id=?", (int(sys.argv[1]),)).fetchone()
    else:
        c = conn.execute("SELECT * FROM complaints ORDER BY id DESC LIMIT 1").fetchone()
    if not c:
        print("No such complaint.")
        return
    a = conn.execute("SELECT * FROM assets WHERE asset_id=?", (c["asset_id"],)).fetchone()
    n = conn.execute("SELECT COUNT(*) FROM complaints WHERE asset_id=?", (c["asset_id"],)).fetchone()[0]
    r = conn.execute("SELECT COUNT(*) FROM repairs WHERE asset_id=?", (c["asset_id"],)).fetchone()[0]

    print(LINE)
    print(f"Database file : {os.path.abspath(DB_PATH)}")
    print(f"Table         : complaints, row id {c['id']} (the citizen's reference number)")
    print(LINE)
    rows = [
        ("Typed text", c["text"]),
        ("Cleaned text", c["clean_text"]),
        ("Category", c["category"]),
        ("Pin location", f"{c['lat']:.6f}, {c['lng']:.6f}"),
        ("Reported at", c["created_at"]),
        ("Reported by", c["reporter"]),
        ("Severity (1-5)", c["severity"]),
        ("Privacy consent", c["consent_at"] or "not recorded"),
        ("Linked to asset", f"{c['asset_id']}  {a['name'] if a else ''}"),
        ("Match score", f"{c['match_score']:.2f}" if c["match_score"] is not None else "none (new location)"),
        ("Match decision", {"auto": "linked automatically", "review": "waiting for engineer review", "new_asset": "new location registered", "confirmed": "confirmed by an engineer", "duplicate": "duplicate", "seeded": "demo history record"}.get(c["match_status"], c["match_status"])),
        ("Likely cause", f"{c['cause'] or 'pending'}  ({c['cause_source'] or 'not tagged yet'})"),
        ("Cause reason", c["cause_reason"] or "-"),
    ]
    for k, v in rows:
        print(f"{k:<16}: {v}")

    if c["embedding"]:
        vec = np.frombuffer(c["embedding"], dtype=np.float32)
        head = ", ".join(f"{x:+.3f}" for x in vec[:5])
        print(f"{'Meaning vector':<16}: {len(vec)} numbers from {c['embedding_model']}")
        print(f"{'':<16}  first five: [{head}, ...]")

    print(LINE)
    if c["photo_url"]:
        path = os.path.join(HERE, "uploads", os.path.basename(c["photo_url"]))
        print(f"Photo file    : {path}")
        if os.path.isfile(path):
            from PIL import Image

            with Image.open(path) as img:
                exif = img.getexif()
                print(f"Photo size    : {img.size[0]} x {img.size[1]} px, {os.path.getsize(path) // 1024} KB")
                print(f"Hidden GPS / phone data left in photo: {'NONE' if not len(exif) else len(exif)} ")
        else:
            print("Photo file    : missing on disk")
    else:
        print("Photo         : none attached")
    print(LINE)
    print(f"This asset now has {n} complaints and {r} repairs in its history.")
    print(LINE)


if __name__ == "__main__":
    main()
