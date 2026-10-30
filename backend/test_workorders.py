"""Repair workflow: assign -> start -> fix, and what each role sees."""
import io
import os
import tempfile

os.environ["CITYMEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "test_wo.db")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9/v1")

import pytest
from fastapi.testclient import TestClient

import main
import seed
from db import now

DEMO = {"citizen": ("citizen001", "citizen@123"), "engineer": ("engineer", "engineer@123"),
        "commissioner": ("commissioner", "commissioner@123")}
HERO = "ROAD-2045"


def as_role(role):
    c = TestClient(main.app)
    u, p = DEMO[role]
    c.headers.update({"Authorization": f"Bearer {c.post('/api/auth/login', json={'username': u, 'password': p}).json()['token']}"})
    return c


@pytest.fixture(autouse=True)
def fresh():
    seed.build(keep_cache=False)


def hero_status(cit):
    mine = [c for c in cit.get("/api/me/complaints").json() if c["asset_id"] == HERO]
    assert mine, "demo citizen should have a report on the hero road"
    return mine[0]


def test_seeded_states_and_overdue():
    eng = as_role("engineer")
    wos = eng.get("/api/work-orders").json()
    states = {w["asset_id"]: w for w in wos}
    assert states["LIGHT-778"]["status"] == "assigned"
    assert states["DRAIN-1120"]["status"] == "in_progress" and states["DRAIN-1120"]["overdue"] is True
    assert HERO not in states
    assert wos[0]["overdue"] is True  # overdue jobs come first
    s = eng.get("/api/stats").json()
    assert s["open_work_orders"] == 3 and s["overdue_work_orders"] == 1


def test_full_cycle_and_citizen_sees_each_stage():
    eng, cit = as_role("engineer"), as_role("citizen")
    assert hero_status(cit)["status"] == "Waiting for repair"

    r = eng.post(f"/api/assets/{HERO}/work-orders", json={"contractor": "Contractor B", "repair_type": "permanent",
                                                           "notes": "Rebuild with drain correction"})
    assert r.status_code == 200, r.text
    wo_id = r.json()["work_order_id"]
    d = eng.get(f"/api/assets/{HERO}").json()
    assert d["work_order"]["status"] == "assigned" and d["work_order"]["due_date"] >= now().date().isoformat()
    st = hero_status(cit)
    assert st["status"] == "Repair assigned" and st["target_date"] == d["work_order"]["due_date"]
    assert any("Contractor B" in s["label"] and s["done"] for s in st["steps"])

    assert eng.post(f"/api/work-orders/{wo_id}/start").status_code == 200
    assert hero_status(cit)["status"] == "Work started"

    from PIL import Image

    buf = io.BytesIO(); Image.new("RGB", (64, 48), (90, 90, 90)).save(buf, "JPEG"); buf.seek(0)
    photo = ("after.jpg", buf, "image/jpeg")
    r = eng.post(f"/api/work-orders/{wo_id}/complete", data={"cost": "580000", "notes": "Resurfaced, drain rebuilt"},
                 files={"photo": photo})
    assert r.status_code == 200, r.text
    st = hero_status(cit)
    assert st["status"] == "Fixed" and st["after_photo_url"] and all(s["done"] for s in st["steps"])
    d = eng.get(f"/api/assets/{HERO}").json()
    assert d["work_order"] is None and d["work_orders"][0]["status"] == "completed"
    assert d["timeline"][0]["kind"] == "repair" and d["timeline"][0]["repair_type"] == "permanent"


def test_rules():
    eng = as_role("engineer")
    # already has an open job
    r = eng.post("/api/assets/LIGHT-778/work-orders", json={"contractor": "X", "repair_type": "temporary"})
    assert r.status_code == 422 and "open work order" in r.json()["detail"]
    # bad inputs
    assert eng.post(f"/api/assets/{HERO}/work-orders", json={"contractor": "", "repair_type": "temporary"}).status_code == 422
    assert eng.post(f"/api/assets/{HERO}/work-orders", json={"contractor": "X", "repair_type": "magic"}).status_code == 422
    assert eng.post(f"/api/assets/{HERO}/work-orders", json={"contractor": "X", "due_date": "2020-01-01"}).status_code == 422
    assert eng.post("/api/assets/NOPE-1/work-orders", json={"contractor": "X"}).status_code == 404
    # cannot start twice, cannot complete twice, negative cost refused
    wo = next(w for w in eng.get("/api/work-orders").json() if w["asset_id"] == "DRAIN-1120")
    assert eng.post(f"/api/work-orders/{wo['id']}/start").status_code == 422
    assert eng.post(f"/api/work-orders/{wo['id']}/complete", data={"cost": "-5"}).status_code == 422
    assert eng.post(f"/api/work-orders/{wo['id']}/complete", data={"cost": "20000"}).status_code == 200
    assert eng.post(f"/api/work-orders/{wo['id']}/complete", data={"cost": "20000"}).status_code == 422
    assert eng.post("/api/work-orders/99999/start").status_code == 404


def test_only_engineers_change_work_orders():
    for role in ("citizen", "commissioner"):
        c = as_role(role)
        assert c.post(f"/api/assets/{HERO}/work-orders", json={"contractor": "X"}).status_code == 403
        assert c.post("/api/work-orders/1/start").status_code == 403
        assert c.post("/api/work-orders/1/complete", data={"cost": "1"}).status_code == 403
    assert as_role("citizen").get("/api/work-orders").status_code == 403
    assert as_role("commissioner").get("/api/work-orders").status_code == 200


def test_permanent_fix_ends_stop_patching_advice():
    eng = as_role("engineer")
    assert eng.get(f"/api/assets/{HERO}").json()["cost"]["recommendation"] == "replace"
    wo = eng.post(f"/api/assets/{HERO}/work-orders", json={"contractor": "Contractor B", "repair_type": "permanent"}).json()["work_order_id"]
    eng.post(f"/api/work-orders/{wo}/complete", data={"cost": "580000"})
    d = eng.get(f"/api/assets/{HERO}").json()
    assert d["cost"]["recommendation"] == "fixed" and "Fixed permanently" in d["cost"]["message"]
    assert HERO not in [x["asset_id"] for x in as_role("commissioner").get("/api/overview").json()["stop_patching"]]
    assert eng.get(f"/api/assets/{HERO}/ai-summary").status_code == 200
