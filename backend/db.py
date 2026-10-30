import os
import sqlite3
from datetime import datetime, timedelta, timezone

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
CREATE TABLE IF NOT EXISTS work_orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id         TEXT NOT NULL REFERENCES assets(asset_id),
    status           TEXT NOT NULL CHECK (status IN ('assigned','in_progress','completed','cancelled')),
    contractor       TEXT,
    repair_type      TEXT,
    due_date         TEXT,
    notes            TEXT,
    created_by       TEXT,
    created_at       TEXT,
    started_at       TEXT,
    completed_at     TEXT,
    cost             REAL,
    completion_notes TEXT,
    after_photo_url  TEXT,
    repair_id        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_wo_asset ON work_orders(asset_id);
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('citizen','engineer','commissioner')),
    name          TEXT,
    created_at    TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    username   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_complaints_asset ON complaints(asset_id);
CREATE INDEX IF NOT EXISTS idx_repairs_asset ON repairs(asset_id);
"""


# India Standard Time (no daylight saving, so a fixed offset is exact and needs no tz database)
IST = timezone(timedelta(hours=5, minutes=30), "IST")


def now() -> datetime:
    """Naive IST 'now' used everywhere, so stored ISO strings compare cleanly and dates match India."""
    return datetime.now(IST).replace(tzinfo=None)


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
    ("repairs", "after_photo_url", "TEXT"),
    ("repairs", "work_order_id", "INTEGER"),
    ("complaints", "consent_at", "TEXT"),
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
