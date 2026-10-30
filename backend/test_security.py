"""Privacy and security: photo handling, signed links, login limits, demo access, consent."""
import io
import os
import tempfile
import time

os.environ["CITYMEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "test_sec.db")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9/v1")

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main
import security
import seed
from db import get_conn

DEMO = {"citizen": ("citizen001", "citizen@123"), "engineer": ("engineer", "engineer@123")}


@pytest.fixture(autouse=True)
def fresh():
    seed.build(keep_cache=False)
    security.LIMITER.reset()


def as_role(role):
    c = TestClient(main.app)
    u, p = DEMO[role]
    c.headers.update({"Authorization": f"Bearer {c.post('/api/auth/login', json={'username': u, 'password': p}).json()['token']}"})
    return c


def jpeg_with_gps():
    img = Image.new("RGB", (2400, 1800), (120, 110, 100))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"                          # Make
    exif[0x8825] = {1: "N", 2: (13.0, 1.0, 54.0), 3: "E", 4: (80.0, 10.0, 50.0)}  # GPS
    buf = io.BytesIO(); img.save(buf, "JPEG", exif=exif); buf.seek(0)
    return buf


def report(c, photo=None, consent="true"):
    data = {"text": "big pothole near the bus stop, water stagnant", "category": "road", "lat": 13.0318, "lng": 80.1807}
    if consent:
        data["consent"] = consent
    files = {"photo": photo} if photo else None
    return c.post("/api/complaints", data=data, files=files)


def test_citizen_must_accept_privacy_notice():
    cit = as_role("citizen")
    r = report(cit, consent=None)
    assert r.status_code == 422 and "privacy notice" in r.json()["detail"]
    r = report(cit)
    assert r.status_code == 200
    row = get_conn().execute("SELECT consent_at FROM complaints WHERE id=?", (r.json()["complaint_id"],)).fetchone()
    assert row[0]


def test_non_image_and_oversized_files_rejected():
    cit = as_role("citizen")
    r = report(cit, photo=("evil.jpg", io.BytesIO(b"<script>alert(1)</script>"), "image/jpeg"))
    assert r.status_code == 422 and "not a photo" in r.json()["detail"]
    big = io.BytesIO(b"\xff\xd8" + b"0" * (security.MAX_PHOTO_MB * 1024 * 1024 + 10))
    r = report(cit, photo=("big.jpg", big, "image/jpeg"))
    assert r.status_code == 422 and "larger than" in r.json()["detail"]
    # nothing half-saved
    assert get_conn().execute("SELECT COUNT(*) FROM complaints WHERE photo_url IS NOT NULL").fetchone()[0] == 0


def test_location_metadata_stripped_and_photo_downsized():
    cit = as_role("citizen")
    r = report(cit, photo=("p.jpg", jpeg_with_gps(), "image/jpeg"))
    assert r.status_code == 200, r.text
    stored = get_conn().execute("SELECT photo_url FROM complaints WHERE id=?", (r.json()["complaint_id"],)).fetchone()[0]
    img = Image.open(os.path.join(security.UPLOADS, os.path.basename(stored)))
    assert max(img.size) <= security.MAX_SIDE
    exif = img.getexif()
    assert 0x8825 not in exif and 0x010F not in exif and not img.info.get("exif")


def test_photos_only_through_valid_signed_links():
    cit = as_role("citizen")
    cid = report(cit, photo=("p.jpg", jpeg_with_gps(), "image/jpeg")).json()["complaint_id"]
    mine = next(c for c in cit.get("/api/me/complaints").json() if c["id"] == cid)
    link = mine["photo_url"]
    assert link.startswith("/api/photos/") and "sig=" in link
    anon = TestClient(main.app)
    r = anon.get(link)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    name = link.split("/api/photos/")[1].split("?")[0]
    # the raw upload folder is not served
    assert "image" not in anon.get(f"/uploads/{name}").headers.get("content-type", "")
    # tampered or expired links fail
    assert anon.get(link.replace("sig=", "sig=0")).status_code == 403
    exp = int(time.time()) - 5
    assert anon.get(f"/api/photos/{name}?exp={exp}&sig={security._sig(name, exp)}").status_code == 403
    trick = anon.get("/api/photos/..%2F.secret?exp=9999999999&sig=x")
    assert trick.status_code in (403, 404) or trick.headers["content-type"].startswith("text/html")
    assert security.SECRET.decode() not in trick.text
    # engineers see the same photo through their own signed link
    d = as_role("engineer").get(f"/api/assets/{mine['asset_id']}").json()
    photos = [e["photo_url"] for e in d["timeline"] if e.get("photo_url")]
    assert photos and all(p.startswith("/api/photos/") for p in photos)


def test_login_locks_after_repeated_failures():
    c = TestClient(main.app)
    for _ in range(security.MAX_FAILS):
        assert c.post("/api/auth/login", json={"username": "engineer", "password": "nope"}).status_code == 401
    r = c.post("/api/auth/login", json={"username": "engineer", "password": "engineer@123"})
    assert r.status_code == 429 and "Try again" in r.json()["detail"]
    # other accounts are unaffected
    assert c.post("/api/auth/login", json={"username": "citizen001", "password": "citizen@123"}).status_code == 200


def test_sessions_stored_hashed():
    token = TestClient(main.app).post("/api/auth/login", json={"username": "engineer", "password": "engineer@123"}).json()["token"]
    stored = [r[0] for r in get_conn().execute("SELECT token FROM sessions")]
    assert token not in stored and security.token_hash(token) in stored


def test_demo_access_can_be_turned_off(monkeypatch):
    c = TestClient(main.app)
    assert c.get("/api/health").json()["demo"] is True
    r = c.post("/api/auth/demo", json={"role": "commissioner"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "commissioner"
    assert c.post("/api/auth/demo", json={"role": "admin"}).status_code == 422
    monkeypatch.setattr(main, "DEMO_MODE", False)
    assert c.post("/api/auth/demo", json={"role": "engineer"}).status_code == 404
    assert c.get("/api/health").json()["demo"] is False


def test_security_headers_present():
    h = TestClient(main.app).get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


@pytest.mark.parametrize("path", [
    "/..%2F..%2Fbackend%2F.secret", "/%2e%2e/%2e%2e/backend/.secret", "/..%2F..%2Fbackend%2Fcitymemory.db",
    "/..%2F..%2Fbackend%2Fmain.py", "/%2e%2e%2f%2e%2e%2fbackend%2fauth.py",
])
def test_no_files_outside_the_website_folder(path):
    if not os.path.isdir(main.DIST):
        pytest.skip("frontend not built")
    r = TestClient(main.app).get(path)
    assert r.headers["content-type"].startswith("text/html")  # the app page, never the file
    assert security.SECRET.decode() not in r.text and "CityMemory API" not in r.text
