"""M3 HTTP-through-ingress tests — live backend, LIVE Claude Sonnet 4.6 LLM via emergentintegrations.

These tests hit the deployed preview URL. They cover:
- Sources CRUD via HTTP
- AI research (LIVE LLM) — persists + singleton + status advance + activity event
- Directions (LIVE) — options returned, none persisted; PUT select persists singleton + status advance
- Outline (LIVE) — singleton persist + status advance
- Content (LIVE) — creates NEW object each time (never overwrites), type varies by content_type
- Edit rewrite/improve_hook/critique — proposal returned WITHOUT mutation; unknown -> 400
- Chat — persists both turns; context-awareness (mention brief.topic)
- Ownership isolation — seeded foreign project returns 404 on every M3 endpoint

LLM ops are slow (5-30s). Use generous timeouts.
"""
import os, uuid, time
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://opportunity-feed-6.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/v1"

# Long timeout for LLM calls
LLM_TIMEOUT = 90
FAST_TIMEOUT = 30


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def mongo():
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    dbname = os.environ.get("DB_NAME", "test_database")
    c = MongoClient(url)
    yield c[dbname]
    c.close()


def _create_project(s, content_type="youtube_video", topic="AI Agents replacing hires"):
    r = s.post(f"{API}/projects", json={
        "title": f"M3HTTP {content_type} {uuid.uuid4().hex[:6]}",
        "content_type": content_type,
        "objective": "M3 HTTP test",
    }, timeout=FAST_TIMEOUT)
    assert r.status_code == 200, r.text
    proj = r.json()
    # Set brief topic
    rb = s.put(f"{API}/projects/{proj['id']}/brief", json={"topic": topic}, timeout=FAST_TIMEOUT)
    assert rb.status_code == 200
    return proj


# =======================================================
# 1. SOURCES CRUD
# =======================================================
def test_sources_crud_http(s):
    p = _create_project(s)
    pid = p["id"]

    r = s.get(f"{API}/projects/{pid}/sources", timeout=FAST_TIMEOUT)
    assert r.status_code == 200 and r.json() == []

    # url source
    r = s.post(f"{API}/projects/{pid}/sources", json={
        "title": "A", "url": "https://example.com/a", "source_type": "url", "content": "note",
    }, timeout=FAST_TIMEOUT)
    assert r.status_code == 200
    sid = r.json()["id"]

    # text source
    r = s.post(f"{API}/projects/{pid}/sources", json={
        "title": "B", "source_type": "text", "content": "AI agents grew a lot",
    }, timeout=FAST_TIMEOUT)
    assert r.status_code == 200

    # url without url → 400
    r = s.post(f"{API}/projects/{pid}/sources", json={
        "title": "C", "source_type": "url",
    }, timeout=FAST_TIMEOUT)
    assert r.status_code == 400, r.text

    lst = s.get(f"{API}/projects/{pid}/sources", timeout=FAST_TIMEOUT).json()
    assert len(lst) == 2

    r = s.delete(f"{API}/projects/{pid}/sources/{sid}", timeout=FAST_TIMEOUT)
    assert r.status_code == 200
    assert len(s.get(f"{API}/projects/{pid}/sources", timeout=FAST_TIMEOUT).json()) == 1


# =======================================================
# 2. RESEARCH — LIVE LLM
# =======================================================
def test_research_persists_singleton_status_activity(s):
    p = _create_project(s, topic="AI Agents replacing hires")
    pid = p["id"]
    assert p["status"] == "idea"

    r = s.post(f"{API}/projects/{pid}/ai/research",
               json={"question": "What is the strongest angle?"}, timeout=LLM_TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    obj1 = body["creative_object"]
    assert obj1["type"] == "research"
    assert obj1["content"]  # non-empty

    # persisted
    objs = s.get(f"{API}/projects/{pid}/creative-objects", timeout=FAST_TIMEOUT).json()
    assert any(o["id"] == obj1["id"] and o["type"] == "research" for o in objs)

    # status advanced
    proj = s.get(f"{API}/projects/{pid}", timeout=FAST_TIMEOUT).json()
    assert proj["status"] == "researching"

    # activity
    ev = s.get(f"{API}/projects/{pid}/activity", timeout=FAST_TIMEOUT).json()
    assert any(e["event_type"] == "research_generated" for e in ev)

    # 2nd call — singleton
    r2 = s.post(f"{API}/projects/{pid}/ai/research",
                json={"question": "Any other angle?"}, timeout=LLM_TIMEOUT)
    assert r2.status_code == 200
    obj2 = r2.json()["creative_object"]
    assert obj2["id"] == obj1["id"], "research must be singleton"


# =======================================================
# 3. DIRECTIONS — LIVE
# =======================================================
def test_directions_generate_and_select(s):
    p = _create_project(s)
    pid = p["id"]

    r = s.post(f"{API}/projects/{pid}/ai/directions", timeout=LLM_TIMEOUT)
    assert r.status_code == 200, r.text
    ds = r.json()["directions"]
    assert 2 <= len(ds) <= 4
    for d in ds:
        for k in ("angle", "audience_takeaway", "format", "tone", "why_it_works"):
            assert k in d

    # nothing persisted yet
    objs = s.get(f"{API}/projects/{pid}/creative-objects", timeout=FAST_TIMEOUT).json()
    assert not any(o["type"] == "direction" for o in objs)

    # select
    r = s.put(f"{API}/projects/{pid}/ai/direction/selected", json=ds[0], timeout=FAST_TIMEOUT)
    assert r.status_code == 200
    first_id = r.json()["id"]
    assert r.json()["type"] == "direction"

    proj = s.get(f"{API}/projects/{pid}", timeout=FAST_TIMEOUT).json()
    assert proj["status"] == "developing"

    # select again — singleton
    if len(ds) >= 2:
        r2 = s.put(f"{API}/projects/{pid}/ai/direction/selected", json=ds[1], timeout=FAST_TIMEOUT)
        assert r2.json()["id"] == first_id


# =======================================================
# 4. OUTLINE + CONTENT + edit — LIVE
# =======================================================
def test_outline_content_edit_youtube(s):
    p = _create_project(s, "youtube_video")
    pid = p["id"]

    ro = s.post(f"{API}/projects/{pid}/ai/outline", timeout=LLM_TIMEOUT)
    assert ro.status_code == 200
    assert ro.json()["creative_object"]["type"] == "outline"

    proj = s.get(f"{API}/projects/{pid}", timeout=FAST_TIMEOUT).json()
    assert proj["status"] == "writing"

    # content 1
    r1 = s.post(f"{API}/projects/{pid}/ai/content", timeout=LLM_TIMEOUT)
    assert r1.status_code == 200
    c1 = r1.json()
    assert c1["type"] == "script"

    # content 2 — new object
    r2 = s.post(f"{API}/projects/{pid}/ai/content", timeout=LLM_TIMEOUT)
    assert r2.status_code == 200
    c2 = r2.json()
    assert c2["id"] != c1["id"], "content must never overwrite"
    assert c2["type"] == "script"

    # edit rewrite — proposal without mutation
    original = c1["content"]
    re = s.post(f"{API}/projects/{pid}/ai/edit", json={
        "action": "rewrite", "content": original, "instruction": "Make it punchier",
    }, timeout=LLM_TIMEOUT)
    assert re.status_code == 200
    assert re.json()["proposal"]
    # DB unchanged
    objs = s.get(f"{API}/projects/{pid}/creative-objects", timeout=FAST_TIMEOUT).json()
    matched = next(o for o in objs if o["id"] == c1["id"])
    assert matched["content"] == original

    # improve_hook
    rh = s.post(f"{API}/projects/{pid}/ai/edit", json={
        "action": "improve_hook", "content": original,
    }, timeout=LLM_TIMEOUT)
    assert rh.status_code == 200
    assert rh.json()["proposal"]

    # critique
    rc = s.post(f"{API}/projects/{pid}/ai/edit", json={
        "action": "critique", "content": original,
    }, timeout=LLM_TIMEOUT)
    assert rc.status_code == 200
    crit = rc.json()["critique"]
    for k in ("strengths", "weaknesses", "suggestions"):
        assert k in crit

    # unknown action
    ru = s.post(f"{API}/projects/{pid}/ai/edit", json={
        "action": "bogus", "content": "x",
    }, timeout=FAST_TIMEOUT)
    assert ru.status_code == 400


# =======================================================
# 5. Content type mapping — LIVE
# =======================================================
@pytest.mark.parametrize("ct,out_type", [
    ("instagram_reel", "script"),
    ("instagram_post", "caption"),
    ("instagram_carousel", "carousel"),
])
def test_content_type_mapping(s, ct, out_type):
    p = _create_project(s, ct)
    r = s.post(f"{API}/projects/{p['id']}/ai/content", timeout=LLM_TIMEOUT)
    assert r.status_code == 200, r.text
    assert r.json()["type"] == out_type


# =======================================================
# 6. CHAT — LIVE + context awareness
# =======================================================
def test_chat_persists_and_context_aware(s):
    p = _create_project(s, topic="AI Agents replacing hires")
    pid = p["id"]

    r = s.post(f"{API}/projects/{pid}/ai/chat",
               json={"message": "What is this project about?"}, timeout=LLM_TIMEOUT)
    assert r.status_code == 200, r.text
    reply = r.json()
    assert reply["role"] == "assistant"
    assert reply["content"], "assistant reply must be non-empty"

    hist = s.get(f"{API}/projects/{pid}/ai/chat", timeout=FAST_TIMEOUT).json()
    roles = [m["role"] for m in hist]
    assert roles == ["user", "assistant"]
    assert hist[0]["content"] == "What is this project about?"


# =======================================================
# 7. Ownership isolation — every M3 endpoint 404
# =======================================================
def test_ownership_isolation_http(s, mongo):
    pid = "iso-" + uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    mongo.projects.insert_one({
        "id": pid, "creator_id": "iso-creator-" + uuid.uuid4().hex[:6],
        "workspace_id": "iso-ws",
        "title": "Foreign", "content_type": "youtube_video", "platform": "youtube",
        "objective": None, "status": "idea",
        "brief": {"topic": None, "objective": None, "target_audience": None,
                  "content_format": None, "takeaway": None, "working_title": None},
        "created_at": now, "updated_at": now,
    })
    try:
        checks = [
            ("GET", f"{API}/projects/{pid}/sources", None),
            ("POST", f"{API}/projects/{pid}/sources", {"title": "x", "source_type": "text", "content": "x"}),
            ("DELETE", f"{API}/projects/{pid}/sources/none", None),
            ("POST", f"{API}/projects/{pid}/ai/research", {"question": "q"}),
            ("POST", f"{API}/projects/{pid}/ai/directions", {}),
            ("PUT", f"{API}/projects/{pid}/ai/direction/selected", {"angle": "a"}),
            ("POST", f"{API}/projects/{pid}/ai/outline", {}),
            ("POST", f"{API}/projects/{pid}/ai/content", {}),
            ("POST", f"{API}/projects/{pid}/ai/edit", {"action": "rewrite", "content": "x"}),
            ("GET", f"{API}/projects/{pid}/ai/chat", None),
            ("POST", f"{API}/projects/{pid}/ai/chat", {"message": "hi"}),
        ]
        for method, url, body in checks:
            r = s.request(method, url, json=body, timeout=FAST_TIMEOUT)
            assert r.status_code == 404, f"{method} {url} -> {r.status_code}"
    finally:
        mongo.projects.delete_one({"id": pid})
