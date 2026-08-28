"""M2 HTTP smoke tests hitting the live backend URL (through ingress)."""
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://opportunity-feed-6.preview.emergentagent.com").rstrip("/")
V1 = f"{BASE}/api/v1"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def test_list_projects_ok(s):
    r = s.get(f"{V1}/projects")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_youtube(s):
    r = s.post(f"{V1}/projects", json={
        "title": f"TEST_M2_YT_{uuid.uuid4().hex[:6]}",
        "content_type": "youtube_video",
        "objective": "Get 500k",
    })
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["platform"] == "youtube"
    assert p["status"] == "idea"
    assert p["brief"]["working_title"] == p["title"]
    assert p["brief"]["objective"] == "Get 500k"
    pytest.pid_yt = p["id"]


@pytest.mark.parametrize("ct,plat", [
    ("instagram_reel", "instagram"),
    ("instagram_post", "instagram"),
    ("instagram_carousel", "instagram"),
])
def test_content_type_platform_maps(s, ct, plat):
    r = s.post(f"{V1}/projects", json={"title": f"TEST_M2_{ct}", "content_type": ct})
    assert r.status_code == 200, r.text
    assert r.json()["platform"] == plat


def test_bad_content_type(s):
    r = s.post(f"{V1}/projects", json={"title": "x", "content_type": "tiktok"})
    assert r.status_code == 400


def test_get_project(s):
    r = s.get(f"{V1}/projects/{pytest.pid_yt}")
    assert r.status_code == 200
    assert r.json()["id"] == pytest.pid_yt


def test_get_nonexistent_404(s):
    r = s.get(f"{V1}/projects/does-not-exist-xyz")
    assert r.status_code == 404


def test_patch_title_bumps_updated(s):
    orig = s.get(f"{V1}/projects/{pytest.pid_yt}").json()["updated_at"]
    r = s.patch(f"{V1}/projects/{pytest.pid_yt}", json={"title": "TEST_M2_YT_updated"})
    assert r.status_code == 200
    assert r.json()["title"] == "TEST_M2_YT_updated"
    assert r.json()["updated_at"] >= orig


def test_patch_status_valid_and_invalid(s):
    r = s.patch(f"{V1}/projects/{pytest.pid_yt}", json={"status": "researching"})
    assert r.status_code == 200 and r.json()["status"] == "researching"
    r = s.patch(f"{V1}/projects/{pytest.pid_yt}", json={"status": "bogus"})
    assert r.status_code == 400


def test_brief_partial_updates_preserve(s):
    pid = pytest.pid_yt
    r = s.put(f"{V1}/projects/{pid}/brief", json={
        "topic": "AI Agents", "target_audience": "Founders", "takeaway": "Try one",
    })
    assert r.status_code == 200
    b = r.json()["brief"]
    assert b["topic"] == "AI Agents" and b["target_audience"] == "Founders"

    # partial: only content_format
    r = s.put(f"{V1}/projects/{pid}/brief", json={"content_format": "Experiment"})
    b = r.json()["brief"]
    assert b["content_format"] == "Experiment"
    assert b["topic"] == "AI Agents"  # preserved

    # refetch persistence
    b2 = s.get(f"{V1}/projects/{pid}").json()["brief"]
    assert b2["topic"] == "AI Agents"
    assert b2["content_format"] == "Experiment"


def test_creative_object_crud(s):
    pid = pytest.pid_yt
    r = s.get(f"{V1}/projects/{pid}/creative-objects")
    assert r.status_code == 200
    initial = len(r.json())

    r = s.post(f"{V1}/projects/{pid}/creative-objects",
               json={"type": "notes", "title": "Rough", "content": "body"})
    assert r.status_code == 200, r.text
    oid = r.json()["id"]

    # invalid type
    r = s.post(f"{V1}/projects/{pid}/creative-objects",
               json={"type": "poem", "title": "x", "content": "y"})
    assert r.status_code == 400

    # update
    r = s.patch(f"{V1}/projects/{pid}/creative-objects/{oid}", json={"content": "updated"})
    assert r.status_code == 200
    assert r.json()["content"] == "updated"

    # list has +1
    lst = s.get(f"{V1}/projects/{pid}/creative-objects").json()
    assert len(lst) == initial + 1

    # delete
    r = s.delete(f"{V1}/projects/{pid}/creative-objects/{oid}")
    assert r.status_code == 200
    lst2 = s.get(f"{V1}/projects/{pid}/creative-objects").json()
    assert all(o["id"] != oid for o in lst2)


def test_activity_events(s):
    events = s.get(f"{V1}/projects/{pytest.pid_yt}/activity").json()
    types = {e["event_type"] for e in events}
    for t in ("project_created", "brief_updated", "project_status_changed", "creative_object_created"):
        assert t in types, f"missing {t}, got {types}"


def test_discard_hides(s):
    r = s.patch(f"{V1}/projects/{pytest.pid_yt}", json={"status": "discarded"})
    assert r.status_code == 200
    lst = s.get(f"{V1}/projects").json()
    assert all(p["id"] != pytest.pid_yt for p in lst)


def test_ownership_isolation_direct_seed():
    """Seed a foreign project in Mongo and confirm the demo user can't reach it."""
    from pymongo import MongoClient
    from datetime import datetime, timezone
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    cl = MongoClient(mongo_url)
    db = cl[db_name]
    pid = "iso-" + uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    db.projects.insert_one({
        "id": pid, "creator_id": "other-creator", "workspace_id": "other-ws",
        "title": "Not yours", "content_type": "youtube_video", "platform": "youtube",
        "objective": None, "status": "idea",
        "brief": {"topic": None, "objective": None, "target_audience": None,
                  "content_format": None, "takeaway": None, "working_title": None},
        "created_at": now, "updated_at": now,
    })
    try:
        for path, method, body in [
            (f"/projects/{pid}", "GET", None),
            (f"/projects/{pid}", "PATCH", {"title": "x"}),
            (f"/projects/{pid}/brief", "PUT", {"topic": "x"}),
            (f"/projects/{pid}/creative-objects", "GET", None),
            (f"/projects/{pid}/activity", "GET", None),
        ]:
            r = requests.request(method, f"{V1}{path}", json=body)
            assert r.status_code == 404, f"{method} {path} -> {r.status_code}: {r.text}"
    finally:
        db.projects.delete_one({"id": pid})
        cl.close()
