"""Login, sessions and role-based access.

Roles
  citizen       files complaints, sees only their own complaints and their status
  engineer      works the priority queue, reviews uncertain matches, logs repairs
  commissioner  ward-level overview: spend, stop-patching decisions, contractors

Passwords are hashed with PBKDF2-SHA256 (Python standard library). A login returns a random
session token; send it as `Authorization: Bearer <token>`. Sessions expire after SESSION_HOURS.
"""
import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException

from db import get_conn, now, one
from security import token_hash

ROLES = ("citizen", "engineer", "commissioner")
SESSION_HOURS = int(os.environ.get("CITYMEMORY_SESSION_HOURS", "12"))
_ITER = 200_000

# Demo accounts created by seed.py. Change these before any real use.
DEMO_USERS = [
    ("citizen001", "citizen@123", "citizen", "Priya Sharma"),
    ("engineer", "engineer@123", "engineer", "Arjun Rao"),
    ("commissioner", "commissioner@123", "commissioner", "Meena Iyer"),
]
_OLD_DEMO_NAMES = ("Priya (citizen)", "Ward Engineer", "Zonal Commissioner")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITER).hex()
    return f"pbkdf2${_ITER}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(test, digest)
    except (ValueError, AttributeError):
        return False


def create_user(conn, username, password, role, name):
    if role not in ROLES:
        raise ValueError("unknown role")
    conn.execute("INSERT INTO users (username, password_hash, role, name, created_at) VALUES (?,?,?,?,?)",
                 (username, hash_password(password), role, name, now().isoformat()))


def seed_demo_users(conn):
    for username, password, role, name in DEMO_USERS:
        if not one(conn, "SELECT 1 FROM users WHERE username=?", (username,)):
            create_user(conn, username, password, role, name)
        else:  # databases made by an earlier version used placeholder names
            conn.execute(f"UPDATE users SET name=? WHERE username=? AND name IN ({','.join('?' * len(_OLD_DEMO_NAMES))})",
                         (name, username, *_OLD_DEMO_NAMES))
    conn.commit()


def start_session(conn, u):
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token, username, expires_at) VALUES (?,?,?)",
                 (token_hash(token), u["username"], (now() + timedelta(hours=SESSION_HOURS)).isoformat()))
    conn.commit()
    return token, public(u)


def login(conn, username, password):
    u = one(conn, "SELECT * FROM users WHERE username=?", ((username or "").strip().lower(),))
    if not u or not verify_password(password or "", u["password_hash"]):
        return None
    return start_session(conn, u)


def demo_login(conn, role):
    username = next((u for u, _, r, _ in DEMO_USERS if r == role), None)
    u = one(conn, "SELECT * FROM users WHERE username=?", (username,)) if username else None
    return start_session(conn, u) if u else None


def logout(conn, token):
    conn.execute("DELETE FROM sessions WHERE token=?", (token_hash(token),))
    conn.commit()


def public(u):
    return {"username": u["username"], "role": u["role"], "name": u["name"]}


# ---------------------------------------------------------------- FastAPI dependencies
def _token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in.", headers={"WWW-Authenticate": "Bearer"})
    return authorization.split(" ", 1)[1].strip()


def current_user(authorization: Optional[str] = Header(None)):
    token = _token(authorization)
    conn = get_conn()
    s = one(conn, "SELECT s.expires_at, u.* FROM sessions s JOIN users u USING(username) WHERE s.token=?", (token_hash(token),))
    if s and s["expires_at"] < now().isoformat():
        conn.execute("DELETE FROM sessions WHERE token=?", (token_hash(token),))
        conn.commit()
        s = None
    conn.close()
    if not s:
        raise HTTPException(401, "Session expired. Please log in again.", headers={"WWW-Authenticate": "Bearer"})
    return {**public(s), "token": token}


def require(*roles):
    """Dependency: the logged-in user must have one of these roles."""
    def check(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"This needs a {' or '.join(roles)} account.")
        return user
    return check


CITIZEN = require("citizen")
ENGINEER = require("engineer")
STAFF = require("engineer", "commissioner")
COMMISSIONER = require("commissioner")
ANY = require(*ROLES)
