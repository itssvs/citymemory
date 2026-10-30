"""AI layer tests. The LLM is mocked; embeddings use the small hashing backend."""
import os
import tempfile

os.environ["CITYMEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "test_ai.db")
os.environ["LLM_BASE_URL"] = "http://127.0.0.1:9/v1"  # unreachable -> fallbacks unless mocked
os.environ.setdefault("CITYMEMORY_EMBEDDER", "hash")

import pytest
from fastapi.testclient import TestClient

import ai
import llm
import logic
import main
import patterns
import seed
from db import get_conn

client = TestClient(main.app)
HERO = "ROAD-2045"


@pytest.fixture(autouse=True)
def fresh_db():
    seed.build(keep_cache=False)


@pytest.fixture
def fake_llm(monkeypatch):
    """Route llm.chat to a function the test sets."""
    state = {"reply": None, "calls": 0}

    def chat(system, user, as_json=False, max_tokens=300, timeout=None):
        state["calls"] += 1
        r = state["reply"]
        return r(system, user) if callable(r) else r

    monkeypatch.setattr(llm, "available", lambda force=False: True)
    monkeypatch.setattr(llm, "chat", chat)
    return state


def test_health_reports_ai_status():
    h = client.get("/api/health").json()
    assert h["ai"]["embedder"]["backend"] in ("sbert", "hash", "tfidf")
    assert h["ai"]["llm"]["available"] is False


def test_embeddings_stored_for_every_complaint():
    conn = get_conn()
    from textsim import SIM

    if SIM.is_vector:
        missing = conn.execute("SELECT COUNT(*) FROM complaints WHERE embedding IS NULL").fetchone()[0]
        assert missing == 0


def test_new_complaint_gets_embedding_and_rule_cause_without_llm():
    a = client.get(f"/api/assets/{HERO}").json()["asset"]
    r = client.post("/api/complaints", data={"text": "pothole full of water near the bus stop, drain blocked",
                                             "category": "road", "lat": a["lat"], "lng": a["lng"]}).json()
    conn = get_conn()
    row = conn.execute("SELECT cause, cause_source, embedding FROM complaints WHERE id=?", (r["complaint_id"],)).fetchone()
    assert row["cause"] == "drainage" and row["cause_source"] == "rules"
    from textsim import SIM

    assert (row["embedding"] is not None) == SIM.is_vector


def test_llm_cause_is_used_and_cached(fake_llm):
    fake_llm["reply"] = {"cause": "utility_digging", "reason": "mentions cable trench left open"}
    conn = get_conn()
    out = ai.tag_complaint(conn, "trench for cable left open on the road", "trench cable", "road")
    assert out == ("utility_digging", "mentions cable trench left open", "llm")
    ai.tag_complaint(conn, "trench for cable left open on the road", "trench cable", "road")
    assert fake_llm["calls"] == 1  # second answer came from the cache


def test_llm_cause_outside_the_list_falls_back_to_rules(fake_llm):
    fake_llm["reply"] = {"cause": "aliens", "reason": "?"}
    cause, _, source = ai.tag_complaint(get_conn(), "drain overflowing after rain", "drain overflow after rain", "road")
    assert source == "rules" and cause == "drainage"


def test_summary_with_invented_number_is_rejected(fake_llm):
    fake_llm["reply"] = "This road failed 99 times and cost Rs 12345678."
    out = client.get(f"/api/assets/{HERO}/ai-summary").json()
    assert out["source"] == "template"


def test_summary_using_only_record_numbers_is_accepted(fake_llm):
    def reply(system, user):
        import json

        f = json.loads(user)
        return (f"{f['asset']} has failed {f['failures_total']} times, with {f['citizen_complaints']} complaints. "
                f"Patching has cost Rs {f['patch_spend_rupees']:,}. Plan a permanent fix.")

    fake_llm["reply"] = reply
    out = client.get(f"/api/assets/{HERO}/ai-summary").json()
    assert out["source"] == "llm" and "Plan a permanent fix" in out["text"]


def test_patterns_find_cross_asset_drainage_cluster():
    res = client.get("/api/patterns").json()
    assert res["patterns"], res
    drainage = [p for p in res["patterns"] if p["cross_type"]]
    assert drainage, "expected a pattern spanning roads and drains"
    p = drainage[0]
    assert len(p["assets"]) >= 2 and p["size"] >= patterns.MIN_SIZE and p["examples"]


def test_pattern_labels_from_llm(fake_llm):
    fake_llm["reply"] = {"label": "Drain overflow damaging roads", "description": "Blocked drains flood nearby roads."}
    res = client.get("/api/patterns").json()
    assert any(p["label"] == "Drain overflow damaging roads" and p["label_source"] == "llm" for p in res["patterns"])


def test_reset_keeps_llm_tags(fake_llm):
    fake_llm["reply"] = {"cause": "drainage", "reason": "water from blocked drain"}
    conn = get_conn()
    c = conn.execute("SELECT id, text, clean_text, category FROM complaints LIMIT 1").fetchone()
    ai.tag_complaint(conn, c["text"], c["clean_text"], c["category"])
    seed.build(keep_cache=True)
    conn = get_conn()
    src = conn.execute("SELECT cause_source FROM complaints WHERE text=? LIMIT 1", (c["text"],)).fetchone()[0]
    assert src == "llm"
