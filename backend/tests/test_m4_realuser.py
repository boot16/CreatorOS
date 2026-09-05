"""M4 tests — Real user foundation.
- Onboarding creates a persistent CreatorDNA v1.
- Creator Context service returns the right shape.
- Feed/opportunity legacy routes DO NOT leak Alex data to authenticated real users.
- Project + AI endpoints stay ownership-scoped.
- Demo mode remains functional.

Auth is mocked at the session-cookie level: we insert real user/workspace/creator
directly into the DB and set the SID cookie on the TestClient.

LLM is mocked so `POST /v1/onboarding` completes without hitting the network.
"""
import os, sys, uuid, secrets
from datetime import datetime, timezone, timedelta

sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database_m4')
os.environ.setdefault('EMERGENT_LLM_KEY', 'x')
os.environ.setdefault('APP_ENCRYPTION_KEY', 'Ah8FVpGr9tYq6cV2s7bH3nD1kX0mLpQeR4uJ_wZcYvA=')

import pytest
from pymongo import MongoClient


@pytest.fixture
def cleandb():
    """Reset ONLY the M4 tables we touch. Uses live DB (shared with server)."""
    client = MongoClient(os.environ["MONGO_URL"])
    d = client[os.environ["DB_NAME"]]
    yield d
    # Cleanup users/workspaces/creators/sessions/DNAs created by these tests
    d.users.delete_many({"id": {"$regex": "^m4-"}})
    d.workspaces.delete_many({"id": {"$regex": "^m4-"}})
    d.workspace_members.delete_many({"workspace_id": {"$regex": "^m4-"}})
    d.creators.delete_many({"id": {"$regex": "^m4-"}})
    d.sessions.delete_many({"user_id": {"$regex": "^m4-"}})
    d.creator_dna_snapshots.delete_many({"creator_id": {"$regex": "^m4-"}})
    d.projects.delete_many({"creator_id": {"$regex": "^m4-"}})
    d.creative_objects.delete_many({"project_id": {"$regex": "^m4-"}})
    client.close()


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch):
    """Stub dna_generator's structured LLM call so onboarding is fast+deterministic."""
    from services import dna_generator as dg

    async def fake_structured(system, user, session_id, schema, model_id=None, max_retries=1):
        return schema.model_validate({
            "creator_types": ["youtuber", "educator"],
            "topics": ["AI tools", "startups"],
            "subtopics": ["prompt engineering"],
            "content_pillars": ["Experiments", "Tutorials", "Reviews"],
            "audience": {
                "description": "College students learning AI and beginner developers.",
                "interests": ["AI agents", "python"],
                "experience_level": "beginner",
            },
            "platforms": ["youtube"],
            "preferred_formats": ["experiment", "tutorial"],
            "voice": {
                "tone": ["direct", "curious"],
                "characteristics": ["first-person", "practical"],
                "style_notes": "Explain complicated AI simply.",
            },
            "goals": ["grow", "educate"],
            "constraints": [],
        })
    monkeypatch.setattr(dg, "call_structured", fake_structured)


def _seed_real_user(db, prefix: str):
    """Insert User→Workspace→Creator→Session directly. Returns (sid, user_id, creator_id)."""
    now = datetime.now(timezone.utc)
    uid = f"m4-{prefix}-user-{uuid.uuid4().hex[:6]}"
    wid = f"m4-{prefix}-ws-{uuid.uuid4().hex[:6]}"
    cid = f"m4-{prefix}-creator-{uuid.uuid4().hex[:6]}"
    db.users.insert_one({
        "id": uid, "email": f"{prefix}@example.com", "name": f"User {prefix.upper()}",
        "picture": None, "google_sub": f"gs-{uid}",
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
    })
    db.workspaces.insert_one({
        "id": wid, "owner_user_id": uid, "name": f"{prefix} ws",
        "slug": f"{prefix}-{uuid.uuid4().hex[:6]}",
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
    })
    db.workspace_members.insert_one({
        "id": str(uuid.uuid4()), "workspace_id": wid, "user_id": uid,
        "role": "owner", "status": "active", "created_at": now.isoformat(),
    })
    db.creators.insert_one({
        "id": cid, "workspace_id": wid, "user_id": uid,
        "display_name": f"User {prefix.upper()}", "handle": None,
        "bio": None, "avatar_url": None, "primary_niche": None,
        "country": None, "languages": [],
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
    })
    sid = secrets.token_urlsafe(24)
    db.sessions.insert_one({
        "sid": sid, "user_id": uid, "email": f"{prefix}@example.com",
        "name": f"User {prefix.upper()}",
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "created_at": now.isoformat(),
    })
    return sid, uid, cid


def _as_user(client, sid):
    """Attach the SID cookie to the (shared) client for a single request context."""
    client.cookies.clear()
    client.cookies.set("creatoros_sid", sid)
    return client


@pytest.fixture
def client(inproc_client):
    inproc_client.cookies.clear()
    return inproc_client


# ============================================================
# Onboarding + Creator Context
# ============================================================
def test_me_before_onboarding_flags_incomplete(client, cleandb):
    sid, uid, cid = _seed_real_user(cleandb, "a")
    r = _as_user(client, sid).get("/api/v1/me")
    assert r.status_code == 200
    body = r.json()
    assert body["is_authenticated"] is True
    assert body["is_demo"] is False
    assert body["onboarding_complete"] is False
    assert body["dna_status"] == "not_computed"


def test_onboarding_creates_dna_and_makes_me_complete(client, cleandb):
    sid, uid, cid = _seed_real_user(cleandb, "b")
    r = _as_user(client, sid).post("/api/v1/onboarding", json={
        "creator_types": ["youtuber"],
        "onboarding_text": "I'm a CS student wanting to teach AI simply.",
        "goals": ["grow"], "platforms": ["youtube"],
    })
    assert r.status_code == 200, r.text
    ctx = r.json()
    assert ctx["has_dna"] is True
    assert ctx["dna"]["creator_types"] == ["youtuber", "educator"]
    # me now shows onboarding_complete
    r = _as_user(client, sid).get("/api/v1/me")
    assert r.json()["onboarding_complete"] is True
    assert r.json()["dna_status"] == "ready"


def test_creator_context_scoped_to_caller(client, cleandb):
    sid_a, _, _ = _seed_real_user(cleandb, "x")
    sid_b, _, _ = _seed_real_user(cleandb, "y")
    _as_user(client, sid_a).post("/api/v1/onboarding", json={
        "creator_types": ["educator"],
        "onboarding_text": "Physics tutor targeting high schoolers.",
    })
    a_ctx = _as_user(client, sid_a).get("/api/v1/creator-context").json()
    b_ctx = _as_user(client, sid_b).get("/api/v1/creator-context").json()
    assert a_ctx["has_dna"] is True
    assert b_ctx["has_dna"] is False
    # B's creator id must not equal A's
    assert a_ctx["creator"]["id"] != b_ctx["creator"]["id"]


def test_onboarding_requires_real_auth(client, cleandb):
    # Anonymous demo caller — no session — should be rejected (require_real_auth)
    client.cookies.clear()
    r = client.post("/api/v1/onboarding", json={
        "creator_types": ["youtuber"], "onboarding_text": "x" * 50,
    })
    assert r.status_code == 401


# ============================================================
# Real users do NOT get Alex Morgan data through legacy routes
# ============================================================
def test_authenticated_user_gets_empty_opportunity_feed(client, cleandb):
    sid, _, _ = _seed_real_user(cleandb, "c")
    r = _as_user(client, sid).get("/api/creators/alex-morgan/opportunities")
    assert r.status_code == 200
    body = r.json()
    # Must be honest empty state, never Alex's seeded items
    assert body.get("status") == "not_computed"
    assert body.get("items") == []


def test_authenticated_user_cannot_load_alex_creator(client, cleandb):
    sid, _, _ = _seed_real_user(cleandb, "d")
    r = _as_user(client, sid).get("/api/creators/alex-morgan")
    assert r.status_code == 404


def test_demo_still_gets_alex(client, cleandb):
    # Demo (no cookie) still sees Alex — this is the seeded demo path we must preserve.
    client.cookies.clear()
    r = client.get("/api/creators/alex-morgan")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "alex-morgan"
    assert body["name"] == "Alex Morgan"


# ============================================================
# Project ownership across two real users
# ============================================================
def test_user_b_cannot_access_user_as_projects(client, cleandb):
    sid_a, uid_a, cid_a = _seed_real_user(cleandb, "p")
    sid_b, uid_b, cid_b = _seed_real_user(cleandb, "q")
    _as_user(client, sid_a).post("/api/v1/onboarding", json={
        "creator_types": ["youtuber"], "onboarding_text": "AI teacher, no channel yet.",
    })
    _as_user(client, sid_b).post("/api/v1/onboarding", json={
        "creator_types": ["writer"], "onboarding_text": "Fiction writer, blogs.",
    })
    # A creates a project
    r = _as_user(client, sid_a).post("/api/v1/projects", json={
        "title": "A's project", "content_type": "youtube_video",
    })
    pid = r.json()["id"]
    # A can read it
    assert _as_user(client, sid_a).get(f"/api/v1/projects/{pid}").status_code == 200
    # B must NOT
    assert _as_user(client, sid_b).get(f"/api/v1/projects/{pid}").status_code == 404
    # B's list does not include A's project
    b_list = _as_user(client, sid_b).get("/api/v1/projects").json()
    assert all(p["id"] != pid for p in b_list)
    # A's list does include it
    a_list = _as_user(client, sid_a).get("/api/v1/projects").json()
    assert any(p["id"] == pid for p in a_list)


def test_project_persists_across_logout_login_cycle(client, cleandb):
    sid, uid, _ = _seed_real_user(cleandb, "r")
    _as_user(client, sid).post("/api/v1/onboarding", json={
        "creator_types": ["youtuber"], "onboarding_text": "Just starting a channel.",
    })
    r = _as_user(client, sid).post("/api/v1/projects", json={
        "title": "Persist me", "content_type": "youtube_video",
    })
    pid = r.json()["id"]
    # Logout (revoke session)
    _as_user(client, sid).post("/api/auth/logout")
    # Simulate re-login: create a NEW session for same user
    new_sid = secrets.token_urlsafe(24)
    cleandb.sessions.insert_one({
        "sid": new_sid, "user_id": uid, "email": "r@example.com", "name": "User R",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    projs = _as_user(client, new_sid).get("/api/v1/projects").json()
    assert any(p["id"] == pid for p in projs)


# ============================================================
# Demo mode still fully functional
# ============================================================
def test_demo_me_still_works(client, cleandb):
    client.cookies.clear()
    r = client.get("/api/v1/me")
    body = r.json()
    assert body["is_demo"] is True
    assert body["creator"]["id"] == "alex-morgan"
    assert body["onboarding_complete"] is True  # demo is auto-onboarded


def test_demo_projects_still_work(client, cleandb):
    client.cookies.clear()
    r = client.post("/api/v1/projects", json={
        "title": "Demo M4 project", "content_type": "youtube_video",
    })
    assert r.status_code == 200
    assert r.json()["creator_id"] == "alex-morgan"
    # Cleanup this demo project
    pid = r.json()["id"]
    cleandb.projects.delete_one({"id": pid})
    cleandb.activity_events.delete_many({"project_id": pid})
