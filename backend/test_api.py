import os
import tempfile

os.environ["CITYMEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest
from fastapi.testclient import TestClient

import main
import seed

client = TestClient(main.app)
HERO = "ROAD-2045"


@pytest.fixture(autouse=True)
def fresh_db():
    seed.build()


def hero_pos():
    a = client.get(f"/api/assets/{HERO}").json()["asset"]
    return a["lat"], a["lng"]


def post(text, category="road", lat=None, lng=None, reporter=None):
    data = {"text": text, "category": category, "lat": lat, "lng": lng}
    if reporter:
        data["reporter"] = reporter
    return client.post("/api/complaints", data=data)


def test_hero_is_recurring_and_recommended_for_replacement():
    d = client.get(f"/api/assets/{HERO}").json()
    assert d["stats"]["recurring"] is True
    assert d["cause"]["primary"] == "drainage"
    assert d["cost"]["recommendation"] == "replace"
    assert d["failure_window"]["available"] is True
    assert len(d["priority"]["components"]) == 5
    ranked = [a["asset_id"] for a in client.get("/api/priority?limit=3").json()]
    assert HERO in ranked


def test_rejects_short_text_and_bad_category():
    lat, lng = hero_pos()
    assert post("hole", lat=lat, lng=lng).status_code == 422
    assert post("big pothole near bus stop", category="bridge", lat=lat, lng=lng).status_code == 422


def test_known_spot_links_automatically_with_history():
    lat, lng = hero_pos()
    r = post("huge pothole near the bus stop full of rain water", lat=lat + 0.00005, lng=lng)
    body = r.json()
    assert r.status_code == 200, body
    assert body["status"] == "auto"
    assert body["asset_id"] == HERO
    assert "Reported" in body["history"]


def test_differently_worded_complaint_still_matches():
    lat, lng = hero_pos()
    body = post("crater outside the stop, two wheelers skidding, drain clogged", lat=lat, lng=lng + 0.00008).json()
    assert body["asset_id"] == HERO
    assert body["status"] in ("auto", "review")


def test_far_away_complaint_creates_unregistered_asset():
    lat, lng = hero_pos()
    body = post("new pothole on the service lane", lat=lat + 0.02, lng=lng + 0.02).json()
    assert body["status"] == "new_asset"
    assert body["asset_id"].startswith("ROAD-")
    assert any(c["id"] == body["complaint_id"] for c in client.get("/api/review").json())


def test_category_filter_keeps_drain_and_road_apart():
    lat, lng = hero_pos()
    body = post("drain blocked and overflowing near the bus stop", category="drain", lat=lat, lng=lng).json()
    assert body["asset_id"].startswith("DRAIN-")


def test_same_reporter_duplicate_is_not_stored_twice():
    lat, lng = hero_pos()
    first = post("pothole near the bus stop again after rain", lat=lat, lng=lng, reporter="tester").json()
    second = post("pothole near bus stop again after the rain", lat=lat, lng=lng, reporter="tester").json()
    assert second["status"] == "duplicate"
    assert second["complaint_id"] == first["complaint_id"]


def test_review_reassign_and_cleanup():
    lat, lng = hero_pos()
    body = post("new pothole on the service lane", lat=lat + 0.02, lng=lng + 0.02).json()
    placeholder = body["asset_id"]
    r = client.post(f"/api/complaints/{body['complaint_id']}/review", json={"action": "reassign", "asset_id": HERO})
    assert r.json()["asset_id"] == HERO
    assert client.get(f"/api/assets/{placeholder}").status_code == 404


def test_logging_a_repair_appears_on_timeline():
    r = client.post("/api/repairs", json={"asset_id": HERO, "repair_type": "permanent", "cost": 580000,
                                          "contractor": "Contractor B", "notes": "full reconstruction with drain"})
    assert r.status_code == 200
    tl = client.get(f"/api/assets/{HERO}").json()["timeline"]
    assert tl[0]["kind"] == "repair" and tl[0]["repair_type"] == "permanent"


def test_search_finds_history():
    res = client.get("/api/search", params={"q": "drain overflowing"}).json()
    assert res and any(r["kind"] == "complaint" for r in res)


def test_contractors_and_backtest():
    cs = client.get("/api/contractors").json()
    a = next(c for c in cs if c["contractor"] == "Contractor A")
    b = next(c for c in cs if c["contractor"] == "Contractor B")
    assert a["avg_days_lasted"] < b["avg_days_lasted"]
    bt = client.get("/api/backtest").json()
    assert bt["tested_assets"] > 0 and 0 <= bt["hit_rate"] <= 1
