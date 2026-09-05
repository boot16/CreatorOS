"""M4 HTTP-through-ingress tests.

Exercises the live preview URL end-to-end. Real-user auth is simulated by
inserting session/user/workspace/creator docs directly into Mongo and setting
the `creatoros_sid` cookie. LLM is LIVE for the one onboarding call we make
(spaced within the 10/hr onboarding rate limit).
"""
import os
import sys
import uuid
import secrets
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    d = c[DB_NAME]
    # Cleanup all m4http-prefixed rows
    for coll in ["users", "workspaces", "workspace_members", "creators",
                 "sessions", "creator_dna_snapshots", "projects", "activity_events"]:
        d[coll].delete_many({"id": {"$regex": "^m4http-"}})
    d.sessions.delete_many({"user_id": {"$regex": "^m4http-"}})
    d.workspace_members.delete_many({"user_id": {"$regex": "^m4http-"}})
    d.creators.delete_many({"user_id": {"$regex": "^m4http-"}})
    d.creator_dna_snapshots.delete_many({"creator_id": {"$regex": "^m4http-"}})
    d.projects.delete_many({"creator_id": {"$regex": "^m4http-"}})
    c.close()


def _seed_user(db, prefix: str):
    now = datetime.now(timezone.utc)
    uid = f"m4http-{prefix}-user-{uuid.uuid4().hex[:6]}"
    wid = f"m4http-{prefix}-ws-{uuid.uuid4().hex[:6]}"
    cid = f"m4http-{prefix}-creator-{uuid.uuid4().hex[:6]}"
    db.users.insert_one({
        "id": uid, "email": f"{prefix}@m4http.test", "name": f"User {prefix.upper()}",
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
        "display_name": f"User {prefix.upper()}", "handle": None, "bio": None,
        "avatar_url": None, "primary_niche": None, "country": None, "languages": [],
        "created_at": now.isoformat(), "updated_at": now.isoformat(),
    })
    sid = secrets.token_urlsafe(24)
    db.sessions.insert_one({
        "sid": sid, "user_id": uid, "email": f"{prefix}@m4http.test",
        "name": f"User {prefix.upper()}",
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "created_at": now.isoformat(),
    })
    return sid, uid, cid


def _sess(sid=None):
    s = requests.Session()
    if sid:
        s.cookies.set("creatoros_sid", sid, domain=BASE_URL.split("//")[1])
    return s


# -----------------------------------------------------------
# Demo mode contract
# -----------------------------------------------------------
def test_demo_me_returns_alex():
    r = requests.get(f"{BASE_URL}/api/v1/me")
    assert r.status_code == 200
    b = r.json()
    assert b["is_demo"] is True
    assert b["is_authenticated"] is False
    assert b["onboarding_complete"] is True
    assert b["creator"]["id"] == "alex-morgan"


def test_demo_creator_context_returns_alex_dna():
    r = requests.get(f"{BASE_URL}/api/v1/creator-context")
    assert r.status_code == 200
    b = r.json()
    assert b["is_demo"] is True
    assert b["has_creator"] is True
    assert b["has_dna"] is True


def test_demo_alex_creator_route_still_works():
    r = requests.get(f"{BASE_URL}/api/creators/alex-morgan")
    assert r.status_code == 200
    assert r.json()["id"] == "alex-morgan"


# -----------------------------------------------------------
# Real-user auth required for onboarding
# -----------------------------------------------------------
def test_onboarding_requires_real_auth():
    r = requests.post(f"{BASE_URL}/api/v1/onboarding", json={
        "creator_types": ["youtuber"],
        "onboarding_text": "x" * 50,
    })
    assert r.status_code == 401


# -----------------------------------------------------------
# Real-user isolation from Alex legacy data
# -----------------------------------------------------------
def test_real_user_gets_404_on_alex_creator(db):
    sid, _, _ = _seed_user(db, "iso1")
    r = _sess(sid).get(f"{BASE_URL}/api/creators/alex-morgan")
    assert r.status_code == 404


def test_real_user_gets_empty_opportunity_feed(db):
    sid, _, _ = _seed_user(db, "iso2")
    r = _sess(sid).get(f"{BASE_URL}/api/creators/alex-morgan/opportunities")
    assert r.status_code == 200
    b = r.json()
    assert b.get("status") == "not_computed"
    assert b.get("items") == []


def test_real_user_me_flags_incomplete_before_onboarding(db):
    sid, _, _ = _seed_user(db, "iso3")
    r = _sess(sid).get(f"{BASE_URL}/api/v1/me")
    assert r.status_code == 200
    b = r.json()
    assert b["is_authenticated"] is True
    assert b["is_demo"] is False
    assert b["onboarding_complete"] is False
    assert b["dna_status"] == "not_computed"


# -----------------------------------------------------------
# Full onboarding flow with LIVE LLM
# -----------------------------------------------------------
def test_full_onboarding_creates_dna_live_llm(db):
    sid, uid, cid = _seed_user(db, "ob1")
    r = _sess(sid).post(f"{BASE_URL}/api/v1/onboarding", json={
        "creator_types": ["youtuber", "educator"],
        "onboarding_text": "I am a college student building AI tutorials to explain "
                           "complicated concepts simply to other CS students.",
        "goals": ["grow", "educate"],
        "platforms": ["youtube"],
        "preferred_formats": ["experiment", "tutorial"],
        "intended_audience": "CS students",
    }, timeout=90)
    assert r.status_code == 200, r.text
    ctx = r.json()
    assert ctx["has_dna"] is True
    dna = ctx["dna"]
    assert isinstance(dna.get("creator_types"), list) and len(dna["creator_types"]) > 0
    assert isinstance(dna.get("topics"), list) and len(dna["topics"]) > 0
    assert isinstance(dna.get("audience"), dict)
    assert isinstance(dna["voice"].get("tone"), list) and len(dna["voice"]["tone"]) > 0

    # /me now says ready
    r2 = _sess(sid).get(f"{BASE_URL}/api/v1/me")
    b = r2.json()
    assert b["onboarding_complete"] is True
    assert b["dna_status"] == "ready"

    # /creator-context has_dna
    r3 = _sess(sid).get(f"{BASE_URL}/api/v1/creator-context")
    assert r3.json()["has_dna"] is True


# -----------------------------------------------------------
# Two-user project isolation
# -----------------------------------------------------------
def test_two_user_project_isolation(db):
    sid_a, uid_a, cid_a = _seed_user(db, "ua")
    sid_b, uid_b, cid_b = _seed_user(db, "ub")
    # Insert DNA snapshots manually so we skip live LLM onboarding for isolation test
    now = datetime.now(timezone.utc).isoformat()
    for cid in (cid_a, cid_b):
        db.creator_dna_snapshots.insert_one({
            "id": str(uuid.uuid4()), "creator_id": cid, "version": 1,
            "source": "onboarding_test", "creator_types": ["youtuber"],
            "topics": ["AI"], "subtopics": [], "content_pillars": ["Tutorials"],
            "audience": {"description": "d", "interests": [], "experience_level": "beginner"},
            "platforms": ["youtube"], "preferred_formats": ["tutorial"],
            "voice": {"tone": ["direct"], "characteristics": [], "style_notes": ""},
            "goals": ["grow"], "constraints": [],
            "created_at": now, "updated_at": now,
        })

    # A creates a project
    r = _sess(sid_a).post(f"{BASE_URL}/api/v1/projects", json={
        "title": "A's project", "content_type": "youtube_video",
    })
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    # A can read it
    assert _sess(sid_a).get(f"{BASE_URL}/api/v1/projects/{pid}").status_code == 200

    # B cannot read it
    assert _sess(sid_b).get(f"{BASE_URL}/api/v1/projects/{pid}").status_code == 404

    # B list does not include it
    b_list = _sess(sid_b).get(f"{BASE_URL}/api/v1/projects").json()
    assert all(p["id"] != pid for p in b_list)

    # A list includes it
    a_list = _sess(sid_a).get(f"{BASE_URL}/api/v1/projects").json()
    assert any(p["id"] == pid for p in a_list)


def test_project_persists_across_logout_relogin(db):
    sid, uid, cid = _seed_user(db, "relogin")
    now = datetime.now(timezone.utc).isoformat()
    db.creator_dna_snapshots.insert_one({
        "id": str(uuid.uuid4()), "creator_id": cid, "version": 1,
        "source": "onboarding_test", "creator_types": ["youtuber"],
        "topics": ["AI"], "subtopics": [], "content_pillars": ["Tutorials"],
        "audience": {"description": "d", "interests": [], "experience_level": "beginner"},
        "platforms": ["youtube"], "preferred_formats": ["tutorial"],
        "voice": {"tone": ["direct"], "characteristics": [], "style_notes": ""},
        "goals": ["grow"], "constraints": [],
        "created_at": now, "updated_at": now,
    })
    r = _sess(sid).post(f"{BASE_URL}/api/v1/projects", json={
        "title": "Persist me", "content_type": "youtube_video",
    })
    pid = r.json()["id"]

    # Logout
    _sess(sid).post(f"{BASE_URL}/api/auth/logout")

    # New session for same user
    new_sid = secrets.token_urlsafe(24)
    db.sessions.insert_one({
        "sid": new_sid, "user_id": uid, "email": "relogin@m4http.test", "name": "User RELOGIN",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    projs = _sess(new_sid).get(f"{BASE_URL}/api/v1/projects").json()
    assert any(p["id"] == pid for p in projs)
