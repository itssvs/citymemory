"""Login and role permissions."""
import os
import tempfile

os.environ["CITYMEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "test_auth.db")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9/v1")

import pytest
from fastapi.testclient import TestClient

import auth
import main
import seed

DEMO = {"citizen": ("citizen001", "citizen@123"), "engineer": ("engineer", "engineer@123"),
        "commissioner": ("commissioner", "commissioner@123")}


@pytest.fixture(autouse=True)
def fresh_db():
    seed.build(keep_cache=False)


def as_role(role):
    c = TestClient(main.app)
    u, p = DEMO[role]
    c.headers.update({"Authorization": f"Bearer {c.post('/api/auth/login', json={'username': u, 'password': p}).json()['token']}"})
    return c


def test_passwords_are_hashed_not_stored():
    h = auth.hash_password("secret123")
    assert "secret123" not in h and auth.verify_password("secret123", h) and not auth.verify_password("nope", h)


def test_login_wrong_password_rejected():
    c = TestClient(main.app)
    assert c.post("/api/auth/login", json={"username": "engineer", "password": "wrong"}).status_code == 401


def test_no_token_is_401_everywhere_except_health():
    c = TestClient(main.app)
    assert c.get("/api/health").status_code == 200
    for path in ["/api/stats", "/api/priority", "/api/assets/ROAD-2045", "/api/patterns", "/api/overview",
                 "/api/me/complaints", "/api/review", "/api/contractors", "/api/public/assets"]:
        assert c.get(path).status_code == 401, path


@pytest.mark.parametrize("role,path,code", [
    ("citizen", "/api/priority", 403),
    ("citizen", "/api/assets/ROAD-2045", 403),
    ("citizen", "/api/overview", 403),
    ("citizen", "/api/review", 403),
    ("citizen", "/api/public/assets", 200),
    ("citizen", "/api/me/complaints", 200),
    ("engineer", "/api/priority", 200),
    ("engineer", "/api/review", 200),
    ("engineer", "/api/overview", 403),
    ("engineer", "/api/me/complaints", 403),
    ("commissioner", "/api/overview", 200),
    ("commissioner", "/api/contractors", 200),
    ("commissioner", "/api/assets/ROAD-2045", 200),
    ("commissioner", "/api/review", 403),
])
def test_role_permissions(role, path, code):
    assert as_role(role).get(path).status_code == code


def test_only_engineer_can_log_repairs():
    body = {"asset_id": "ROAD-2045", "repair_type": "temporary", "cost": 1000, "contractor": "X"}
    assert as_role("commissioner").post("/api/repairs", json=body).status_code == 403
    assert as_role("citizen").post("/api/repairs", json=body).status_code == 403
    assert as_role("engineer").post("/api/repairs", json=body).status_code == 200


def test_commissioner_cannot_file_complaints():
    r = as_role("commissioner").post("/api/complaints", data={"text": "pothole near bus stop", "category": "road",
                                                              "lat": 13.0318, "lng": 80.1807, "consent": "true"})
    assert r.status_code == 403


def test_citizen_sees_only_own_complaints_and_no_internal_scores():
    cit = as_role("citizen")
    seeded = cit.get("/api/me/complaints").json()
    assert seeded, "demo citizen should have seeded complaints"
    r = cit.post("/api/complaints", data={"text": "pothole full of water near the bus stop", "category": "road",
                                          "lat": 13.0318, "lng": 80.1807, "consent": "true"}).json()
    assert r["match"] is None and "candidates" not in r
    mine = cit.get("/api/me/complaints").json()
    assert len(mine) == len(seeded) + 1 and mine[0]["id"] == r["complaint_id"]
    assert all(c["steps"][0]["label"] == "Submitted" for c in mine)

    # a newly registered citizen sees none of citizen001's complaints
    other = TestClient(main.app)
    t = other.post("/api/auth/register", json={"username": "ravi_k", "password": "ravi12345", "name": "Ravi"}).json()
    other.headers.update({"Authorization": f"Bearer {t['token']}"})
    assert t["user"]["role"] == "citizen" and other.get("/api/me/complaints").json() == []


def test_register_validates_and_cannot_choose_role():
    c = TestClient(main.app)
    assert c.post("/api/auth/register", json={"username": "ab", "password": "longenough", "name": "x"}).status_code == 422
    assert c.post("/api/auth/register", json={"username": "abc", "password": "short", "name": "x"}).status_code == 422
    assert c.post("/api/auth/register", json={"username": "engineer", "password": "longenough", "name": "x"}).status_code == 409
    r = c.post("/api/auth/register", json={"username": "newbie", "password": "longenough", "name": "x", "role": "commissioner"})
    assert r.json()["user"]["role"] == "citizen"


def test_logout_invalidates_token():
    c = as_role("engineer")
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/stats").status_code == 401


def test_overview_numbers():
    o = as_role("commissioner").get("/api/overview").json()
    assert o["stop_patching"] and o["decision"]["assets"] == len(o["stop_patching"])
    assert len(o["complaints_by_month"]) == 12
    assert o["contractors"]["shortest"]["avg_days_lasted"] <= o["contractors"]["longest"]["avg_days_lasted"]


def test_calendar_scoped_by_role():
    from db import now

    month = now().strftime("%Y-%m")
    staff = as_role("engineer").get("/api/calendar", params={"month": month}).json()
    mine = as_role("citizen").get("/api/calendar", params={"month": month}).json()
    assert len(staff["days"]) >= 28 and 0 <= staff["first_weekday"] <= 6
    assert mine["totals"]["complaints"] <= staff["totals"]["complaints"]
    assert as_role("engineer").get("/api/calendar", params={"month": "2026-13"}).status_code == 422
    assert TestClient(main.app).get("/api/calendar").status_code == 401
