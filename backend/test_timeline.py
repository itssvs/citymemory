"""Ward timeline: linking, filters, search, permissions."""
import os
import tempfile

os.environ["CITYMEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "test_tl.db")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9/v1")

import pytest
from fastapi.testclient import TestClient

import main
import seed
from db import now


@pytest.fixture(scope="module", autouse=True)
def fresh():
    seed.build(keep_cache=False)


def client(role):
    c = TestClient(main.app)
    u, p = {"engineer": ("engineer", "engineer@123"), "commissioner": ("commissioner", "commissioner@123"),
            "citizen": ("citizen001", "citizen@123")}[role]
    c.headers.update({"Authorization": f"Bearer {c.post('/api/auth/login', json={'username': u, 'password': p}).json()['token']}"})
    return c


def tl(c, **params):
    r = c.get("/api/timeline", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_staff_only():
    assert TestClient(main.app).get("/api/timeline").status_code == 401
    assert client("citizen").get("/api/timeline").status_code == 403
    assert client("commissioner").get("/api/timeline").status_code == 200


def test_everything_linked_and_newest_first():
    d = tl(client("engineer"), limit=200)
    ev = d["events"]
    assert d["total"] == sum(d["counts"].values())
    assert {e["kind"] for e in ev} == {"complaint", "repair", "job"}
    assert all(e["asset_id"] and e["asset_name"] for e in ev)
    dates = [e["date"] for e in ev]
    assert dates == sorted(dates, reverse=True)
    comp = [e for e in ev if e["kind"] == "complaint"]
    assert any(e["opened_failure"] for e in comp) and any(not e["opened_failure"] for e in comp)
    rep = [e for e in ev if e["kind"] == "repair"]
    assert any(e["failed_again"] and e["lasted_days"] is not None for e in rep)


def test_filters():
    c = client("engineer")
    d = tl(c, types="drain", kinds="repair")
    assert d["events"] and all(e["asset_type"] == "drain" and e["kind"] == "repair" for e in d["events"])
    one = tl(c, asset_id="ROAD-2045")
    assert one["events"] and {e["asset_id"] for e in one["events"]} == {"ROAD-2045"}
    start = (now().date().replace(day=1)).isoformat()
    recent = tl(c, start=start, limit=200)
    assert all(e["date"][:10] >= start for e in recent["events"])
    assert len(recent["months"]) == 24
    assert c.get("/api/timeline", params={"start": "2026-10-31", "end": "2026-01-01"}).status_code == 422
    assert c.get("/api/timeline", params={"types": "bridge"}).status_code == 422
    assert c.get("/api/timeline", params={"asset_id": "NOPE-1"}).status_code == 422


def test_search_by_meaning_and_by_id():
    c = client("engineer")
    d = tl(c, q="water stagnant pothole", kinds="complaint", limit=200)
    assert d["events"] and all(e["match_on"] in ("meaning", "words", "asset") for e in d["events"])
    assert any(e["asset_type"] == "road" for e in d["events"])
    by_id = tl(c, q="LIGHT-778", limit=200)
    assert by_id["events"] and {e["asset_id"] for e in by_id["events"]} == {"LIGHT-778"}
    best = tl(c, q="water stagnant pothole", sort="match")["events"]
    assert [e["match"] for e in best] == sorted((e["match"] for e in best), reverse=True)
    assert tl(c, q="zzqx nothing like this")["total"] == 0
