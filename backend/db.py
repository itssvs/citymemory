import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "CITYMEMORY_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "citymemory.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    asset_id         TEXT PRIMARY KEY,
    type             TEXT NOT NULL,
    name             TEXT NOT NULL,
    ward             TEXT,
    lat              REAL NOT NULL,
    lng              REAL NOT NULL,
    install_year     INTEGER,
    lifespan_years   INTEGER,
    replacement_cost REAL,
    registered       INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS complaints (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id     TEXT NOT NULL REFERENCES assets(asset_id),
    text         TEXT,
    clean_text   TEXT,
    category     TEXT,
    lat          REAL,
    lng          REAL,
    photo_url    TEXT,
    created_at   TEXT,
    reporter     TEXT,
    severity     INTEGER,
    cause        TEXT,
    cause_reason TEXT,
    match_score  REAL,
    match_status TEXT,
    cause_source TEXT,
    embedding    BLOB,
    embedding_model TEXT
);
CREATE TABLE IF NOT EXISTS repairs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id     TEXT NOT NULL REFERENCES assets(asset_id),
    repair_type  TEXT,
    cost         REAL,
    completed_at TEXT,
    contractor   TEXT,
    notes        TEXT
);
CREATE TABLE IF NOT EXISTS llm_cache (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    model      TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_complaints_asset ON complaints(asset_id);
CREATE INDEX IF NOT EXISTS idx_repairs_asset ON repairs(asset_id);
"""


def now() -> datetime:
    """Naive UTC 'now' used everywhere so stored ISO strings compare cleanly."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# columns added after the first version; added in place to older databases
_MIGRATIONS = [
    ("complaints", "cause_source", "TEXT"),
    ("complaints", "embedding", "BLOB"),
    ("complaints", "embedding_model", "TEXT"),
]


def init_db() -> None:
    conn = get_conn()
    conn.executescript(SCHEMA)
    for table, col, typ in _MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    # read-only view of complaints without the binary embedding, used by every API read
    conn.execute(
        "CREATE VIEW IF NOT EXISTS cv AS SELECT id, asset_id, text, clean_text, category, lat, lng, photo_url, "
        "created_at, reporter, severity, cause, cause_reason, cause_source, match_score, match_status FROM complaints"
    )
    conn.commit()
    conn.close()


def rows(conn, sql, args=()):
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def one(conn, sql, args=()):
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None
