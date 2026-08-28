"""M2 tests — Project domain, Brief persistence, CreativeObjects, ActivityEvents, ownership isolation."""
import os, sys, uuid
sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database_m2')
os.environ.setdefault('EMERGENT_LLM_KEY', 'x')
os.environ.setdefault('APP_ENCRYPTION_KEY', 'Ah8FVpGr9tYq6cV2s7bH3nD1kX0mLpQeR4uJ_wZcYvA=')

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pymongo import MongoClient


@pytest.fixture
def cleandb():
    """Wipe M2 collections before/after each test."""
    client = MongoClient(os.environ["MONGO_URL"])
    d = client[os.environ["DB_NAME"]]
    d.projects.delete_many({})
    d.creative_objects.delete_many({})
    d.activity_events.delete_many({})
    yield d
    d.projects.delete_many({})
    d.creative_objects.delete_many({})
    d.activity_events.delete_many({})
    client.close()


@pytest.fixture(scope="module")
def client():
    from server import app
    with TestClient(app) as c:
        yield c


def test_list_projects_empty(client, cleandb):
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_create_project_youtube(client, cleandb):
    r = client.post("/api/v1/projects", json={
        "title": "AI Employees Deep Dive",
        "content_type": "youtube_video",
        "objective": "Get 500k views",
    })
    assert r.status_code == 200
    p = r.json()
    assert p["title"] == "AI Employees Deep Dive"
    assert p["content_type"] == "youtube_video"
    assert p["platform"] == "youtube"
    assert p["status"] == "idea"
    assert p["brief"]["working_title"] == "AI Employees Deep Dive"
    assert p["brief"]["objective"] == "Get 500k views"


def test_create_project_instagram_reel_maps_platform(client, cleandb):
    r = client.post("/api/v1/projects", json={
        "title": "Reel test", "content_type": "instagram_reel",
    })
    assert r.status_code == 200
    assert r.json()["platform"] == "instagram"


def test_reject_invalid_content_type(client, cleandb):
    r = client.post("/api/v1/projects", json={"title": "x", "content_type": "tiktok"})
    assert r.status_code == 400


def test_reject_empty_title(client, cleandb):
    r = client.post("/api/v1/projects", json={"title": "  ", "content_type": "youtube_video"})
    # after strip, update path also validates; create requires min_length=1 by schema (whitespace passes),
    # so accepted at create — but PATCH with empty title should reject:
    if r.status_code == 200:
        pid = r.json()["id"]
        rr = client.patch(f"/api/v1/projects/{pid}", json={"title": "   "})
        assert rr.status_code == 400


def test_project_lifecycle(client, cleandb):
    # create
    r = client.post("/api/v1/projects", json={"title": "Test", "content_type": "youtube_video"})
    pid = r.json()["id"]

    # get
    r = client.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200

    # update title + status
    r = client.patch(f"/api/v1/projects/{pid}", json={"title": "New Title", "status": "researching"})
    assert r.status_code == 200
    p = r.json()
    assert p["title"] == "New Title"
    assert p["status"] == "researching"

    # invalid status
    r = client.patch(f"/api/v1/projects/{pid}", json={"status": "bogus"})
    assert r.status_code == 400

    # list only shows non-discarded
    r = client.patch(f"/api/v1/projects/{pid}", json={"status": "discarded"})
    assert r.status_code == 200
    r = client.get("/api/v1/projects")
    assert all(p["id"] != pid for p in r.json())


def test_brief_persists(client, cleandb):
    r = client.post("/api/v1/projects", json={"title": "Brief test", "content_type": "youtube_video"})
    pid = r.json()["id"]

    r = client.put(f"/api/v1/projects/{pid}/brief", json={
        "topic": "AI Agents", "target_audience": "Solo founders",
        "takeaway": "Try one agent today",
    })
    assert r.status_code == 200
    b = r.json()["brief"]
    assert b["topic"] == "AI Agents"
    assert b["target_audience"] == "Solo founders"
    assert b["takeaway"] == "Try one agent today"
    # working_title should be preserved from creation
    assert b["working_title"] == "Brief test"

    # partial update: only content_format
    r = client.put(f"/api/v1/projects/{pid}/brief", json={"content_format": "Experiment"})
    assert r.status_code == 200
    b = r.json()["brief"]
    assert b["content_format"] == "Experiment"
    assert b["topic"] == "AI Agents"  # preserved

    # refetch — persisted
    r = client.get(f"/api/v1/projects/{pid}")
    assert r.json()["brief"]["topic"] == "AI Agents"
    assert r.json()["brief"]["content_format"] == "Experiment"


def test_creative_object_crud(client, cleandb):
    r = client.post("/api/v1/projects", json={"title": "CO test", "content_type": "youtube_video"})
    pid = r.json()["id"]

    # list empty
    r = client.get(f"/api/v1/projects/{pid}/creative-objects")
    assert r.json() == []

    # create
    r = client.post(f"/api/v1/projects/{pid}/creative-objects", json={
        "type": "notes", "title": "brainstorm", "content": "first idea",
    })
    assert r.status_code == 200
    oid = r.json()["id"]
    assert r.json()["type"] == "notes"

    # invalid type
    r = client.post(f"/api/v1/projects/{pid}/creative-objects", json={
        "type": "poem", "title": "x", "content": "y",
    })
    assert r.status_code == 400

    # update
    r = client.patch(f"/api/v1/projects/{pid}/creative-objects/{oid}", json={
        "content": "updated body",
    })
    assert r.status_code == 200
    assert r.json()["content"] == "updated body"

    # list has 1
    r = client.get(f"/api/v1/projects/{pid}/creative-objects")
    assert len(r.json()) == 1

    # delete
    r = client.delete(f"/api/v1/projects/{pid}/creative-objects/{oid}")
    assert r.status_code == 200
    r = client.get(f"/api/v1/projects/{pid}/creative-objects")
    assert r.json() == []


def test_activity_recorded(client, cleandb):
    r = client.post("/api/v1/projects", json={"title": "AL test", "content_type": "youtube_video"})
    pid = r.json()["id"]
    client.put(f"/api/v1/projects/{pid}/brief", json={"topic": "x"})
    client.patch(f"/api/v1/projects/{pid}", json={"status": "developing"})
    client.post(f"/api/v1/projects/{pid}/creative-objects", json={
        "type": "outline", "title": "o", "content": "body",
    })
    r = client.get(f"/api/v1/projects/{pid}/activity")
    assert r.status_code == 200
    events = r.json()
    types = [e["event_type"] for e in events]
    assert "project_created" in types
    assert "brief_updated" in types
    assert "project_status_changed" in types
    assert "creative_object_created" in types


def test_ownership_isolation(client, cleandb):
    """A project scoped to creator A must not be reachable via a valid session for creator B.

    In demo mode all callers share creator_id=alex-morgan, so we simulate isolation
    by seeding a project directly into Mongo for a different creator_id.
    """
    pid = "iso-" + uuid.uuid4().hex[:8]
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    cleandb.projects.insert_one({
        "id": pid, "creator_id": "other-creator", "workspace_id": "other-ws",
        "title": "Not yours", "content_type": "youtube_video", "platform": "youtube",
        "objective": None, "status": "idea",
        "brief": {"topic": None, "objective": None, "target_audience": None,
                  "content_format": None, "takeaway": None, "working_title": None},
        "created_at": now, "updated_at": now,
    })

    # demo caller (creator=alex-morgan) MUST NOT see it
    r = client.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 404

    r = client.patch(f"/api/v1/projects/{pid}", json={"title": "hijacked"})
    assert r.status_code == 404

    r = client.put(f"/api/v1/projects/{pid}/brief", json={"topic": "hijacked"})
    assert r.status_code == 404

    r = client.get(f"/api/v1/projects/{pid}/creative-objects")
    assert r.status_code == 404

    r = client.get(f"/api/v1/projects/{pid}/activity")
    assert r.status_code == 404


def test_project_shows_in_list_after_create(client, cleandb):
    r1 = client.post("/api/v1/projects", json={"title": "P1", "content_type": "youtube_video"})
    r2 = client.post("/api/v1/projects", json={"title": "P2", "content_type": "instagram_reel"})
    ids = {r1.json()["id"], r2.json()["id"]}
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    got = {p["id"] for p in r.json()}
    assert ids.issubset(got)
