"""M3 tests — Project-Aware AI.

We mock the LLM layer at services/project_ai's imports so tests don't hit an external API.
Focus:
  - Ownership on every AI endpoint (foreign creator → 404, never leaks existence).
  - Research persists as CreativeObject(type=research) and sources CRUD.
  - Directions generation returns options; PUT selected persists a CreativeObject(type=direction).
  - Outline generation persists CreativeObject(type=outline).
  - Content generation creates a NEW CreativeObject (never overwrites existing).
  - Edit action returns proposal WITHOUT mutating the CreativeObject.
  - Critique returns structured critique.
  - Chat persists user turn even when AI fails; assistant reply persists on success.
  - AI failure never destroys existing content.
"""
import os, sys, uuid, asyncio
sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database_m3')
os.environ.setdefault('EMERGENT_LLM_KEY', 'x')
os.environ.setdefault('APP_ENCRYPTION_KEY', 'Ah8FVpGr9tYq6cV2s7bH3nD1kX0mLpQeR4uJ_wZcYvA=')

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient


# ------------- LLM STUB -------------
class _Fake:
    """Namespace for monkeypatched LLM outputs. Set attributes per test to control behavior."""
    research_out = None
    directions_out = None
    outline_out = None
    content_out = None
    edit_out = None
    critique_out = None
    chat_out = None
    fail = None  # str -> raise AppError on that task


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch):
    """Patch project_ai's `call_structured` and `call_text` to return fixture data."""
    from services import project_ai as pai
    from core.errors import AppError, Codes

    async def fake_structured(system, user, session_id, schema, model_id=None, max_retries=1):
        # Route by session_id suffix
        if "research" in session_id:
            if _Fake.fail == "research":
                raise AppError(Codes.UPSTREAM_ERROR, "AI down", status_code=502)
            return schema.model_validate(_Fake.research_out or _DEFAULT_RESEARCH)
        if "directions" in session_id:
            if _Fake.fail == "directions":
                raise AppError(Codes.UPSTREAM_ERROR, "AI down", status_code=502)
            return schema.model_validate(_Fake.directions_out or _DEFAULT_DIRECTIONS)
        if "outline" in session_id:
            if _Fake.fail == "outline":
                raise AppError(Codes.UPSTREAM_ERROR, "AI down", status_code=502)
            return schema.model_validate(_Fake.outline_out or _DEFAULT_OUTLINE)
        if "critique" in session_id:
            if _Fake.fail == "critique":
                raise AppError(Codes.UPSTREAM_ERROR, "AI down", status_code=502)
            return schema.model_validate(_Fake.critique_out or _DEFAULT_CRITIQUE)
        raise AssertionError(f"unexpected structured session: {session_id}")

    async def fake_text(system, user, session_id, model_id=None):
        if "content-" in session_id:
            if _Fake.fail == "content":
                raise AppError(Codes.UPSTREAM_ERROR, "AI down", status_code=502)
            return _Fake.content_out or "AI DRAFT CONTENT\n\nHook: something punchy."
        if "edit-" in session_id:
            if _Fake.fail == "edit":
                raise AppError(Codes.UPSTREAM_ERROR, "AI down", status_code=502)
            return _Fake.edit_out or "REWRITTEN CONTENT"
        if "chat" in session_id:
            if _Fake.fail == "chat":
                raise AppError(Codes.UPSTREAM_ERROR, "AI down", status_code=502)
            return _Fake.chat_out or "That's a great question about this project — try angle X."
        raise AssertionError(f"unexpected text session: {session_id}")

    monkeypatch.setattr(pai, "call_structured", fake_structured)
    monkeypatch.setattr(pai, "call_text", fake_text)
    yield
    _Fake.research_out = None
    _Fake.directions_out = None
    _Fake.outline_out = None
    _Fake.content_out = None
    _Fake.edit_out = None
    _Fake.critique_out = None
    _Fake.chat_out = None
    _Fake.fail = None


_DEFAULT_RESEARCH = {
    "summary": "Solid opportunity for a first-person AI experiment.",
    "key_facts": ["AI agents growing 300% YoY"],
    "insights": ["Founders want proof, not hype"],
    "perspectives": ["Skeptic vs believer"],
    "opportunities": ["30-day log format"],
    "open_questions": ["What tools actually work?"],
}

_DEFAULT_DIRECTIONS = {"directions": [
    {"angle": "Replace one hire", "audience_takeaway": "Try it", "format": "experiment", "tone": "direct", "why_it_works": "high stakes"},
    {"angle": "Fail on purpose", "audience_takeaway": "Learn from failure", "format": "log", "tone": "wry", "why_it_works": "counter-narrative"},
]}

_DEFAULT_OUTLINE = {"outline": [
    {"label": "HOOK", "beats": ["Bold claim"]},
    {"label": "BEAT 1", "beats": ["Setup", "Attempt 1"]},
    {"label": "PAYOFF", "beats": ["Result"]},
]}

_DEFAULT_CRITIQUE = {
    "strengths": ["Strong hook"],
    "weaknesses": ["Middle drags"],
    "suggestions": ["Cut section 2 by 40%"],
}


# ------------- DB fixture -------------
@pytest.fixture
def cleandb():
    client = MongoClient(os.environ["MONGO_URL"])
    d = client[os.environ["DB_NAME"]]
    for c in ("projects", "creative_objects", "activity_events",
              "project_sources", "project_chats"):
        d[c].delete_many({})
    yield d
    for c in ("projects", "creative_objects", "activity_events",
              "project_sources", "project_chats"):
        d[c].delete_many({})
    client.close()


@pytest.fixture
def client(inproc_client):
    return inproc_client


def _create_project(client, content_type="youtube_video"):
    r = client.post("/api/v1/projects", json={
        "title": f"M3 {content_type}",
        "content_type": content_type,
        "objective": "Test M3",
    })
    assert r.status_code == 200
    return r.json()


# ============================================================
# Sources CRUD
# ============================================================
def test_sources_crud(client, cleandb):
    p = _create_project(client)
    # list empty
    assert client.get(f"/api/v1/projects/{p['id']}/sources").json() == []
    # add url
    r = client.post(f"/api/v1/projects/{p['id']}/sources", json={
        "title": "Great article", "url": "https://example.com/a", "source_type": "url",
        "content": "Summary from user.",
    })
    assert r.status_code == 200
    sid = r.json()["id"]
    # add text
    r = client.post(f"/api/v1/projects/{p['id']}/sources", json={
        "title": "Pasted note", "source_type": "text", "content": "Some pasted text.",
    })
    assert r.status_code == 200
    # url source without url → 400
    r = client.post(f"/api/v1/projects/{p['id']}/sources", json={
        "title": "Bad", "source_type": "url",
    })
    assert r.status_code == 400
    # list has 2
    lst = client.get(f"/api/v1/projects/{p['id']}/sources").json()
    assert len(lst) == 2
    # delete
    r = client.delete(f"/api/v1/projects/{p['id']}/sources/{sid}")
    assert r.status_code == 200
    lst = client.get(f"/api/v1/projects/{p['id']}/sources").json()
    assert len(lst) == 1


# ============================================================
# Research
# ============================================================
def test_research_persists_and_advances_status(client, cleandb):
    p = _create_project(client)
    assert p["status"] == "idea"
    r = client.post(f"/api/v1/projects/{p['id']}/ai/research", json={"question": "How big is AI agents?"})
    assert r.status_code == 200
    obj = r.json()["creative_object"]
    assert obj["type"] == "research"
    assert "AI agents growing 300%" in obj["content"]
    # Refetch — persistent
    objs = client.get(f"/api/v1/projects/{p['id']}/creative-objects").json()
    assert any(o["type"] == "research" and o["id"] == obj["id"] for o in objs)
    # Status auto-advanced idea → researching
    proj = client.get(f"/api/v1/projects/{p['id']}").json()
    assert proj["status"] == "researching"
    # Activity recorded
    events = client.get(f"/api/v1/projects/{p['id']}/activity").json()
    assert any(e["event_type"] == "research_generated" for e in events)


def test_research_singleton_updates_in_place(client, cleandb):
    p = _create_project(client)
    r1 = client.post(f"/api/v1/projects/{p['id']}/ai/research", json={"question": "q1"}).json()
    r2 = client.post(f"/api/v1/projects/{p['id']}/ai/research", json={"question": "q2"}).json()
    assert r1["creative_object"]["id"] == r2["creative_object"]["id"]


def test_research_failure_does_not_destroy_sources_or_prior_research(client, cleandb):
    p = _create_project(client)
    # seed initial research
    r1 = client.post(f"/api/v1/projects/{p['id']}/ai/research", json={"question": "q1"}).json()
    prior_content = r1["creative_object"]["content"]
    # add sources
    client.post(f"/api/v1/projects/{p['id']}/sources", json={"title": "S", "source_type": "text", "content": "keep me"})

    _Fake.fail = "research"
    r2 = client.post(f"/api/v1/projects/{p['id']}/ai/research", json={"question": "q2"})
    assert r2.status_code == 502
    # Prior research + sources still intact
    objs = client.get(f"/api/v1/projects/{p['id']}/creative-objects").json()
    research = [o for o in objs if o["type"] == "research"]
    assert len(research) == 1
    assert research[0]["content"] == prior_content
    srcs = client.get(f"/api/v1/projects/{p['id']}/sources").json()
    assert len(srcs) == 1


# ============================================================
# Directions
# ============================================================
def test_directions_generate_then_select(client, cleandb):
    p = _create_project(client)
    r = client.post(f"/api/v1/projects/{p['id']}/ai/directions")
    assert r.status_code == 200
    ds = r.json()["directions"]
    assert 2 <= len(ds) <= 4
    # NOT saved yet
    objs = client.get(f"/api/v1/projects/{p['id']}/creative-objects").json()
    assert not any(o["type"] == "direction" for o in objs)
    # select one
    picked = ds[0]
    r = client.put(f"/api/v1/projects/{p['id']}/ai/direction/selected", json=picked)
    assert r.status_code == 200
    assert r.json()["type"] == "direction"
    # Status advanced to developing
    proj = client.get(f"/api/v1/projects/{p['id']}").json()
    assert proj["status"] == "developing"
    # Selecting a second direction overwrites (singleton)
    r2 = client.put(f"/api/v1/projects/{p['id']}/ai/direction/selected", json=ds[1])
    assert r2.status_code == 200
    assert r2.json()["id"] == r.json()["id"]


# ============================================================
# Outline + Content
# ============================================================
def test_outline_and_content_persist_and_never_overwrite_content(client, cleandb):
    p = _create_project(client)
    # outline
    r = client.post(f"/api/v1/projects/{p['id']}/ai/outline")
    assert r.status_code == 200
    outline_id = r.json()["creative_object"]["id"]
    assert r.json()["creative_object"]["type"] == "outline"
    # content
    r1 = client.post(f"/api/v1/projects/{p['id']}/ai/content")
    r2 = client.post(f"/api/v1/projects/{p['id']}/ai/content")
    assert r1.json()["id"] != r2.json()["id"], "content generation must never overwrite prior drafts"
    # both should be `script` type since content_type=youtube_video
    assert r1.json()["type"] == "script"
    assert r2.json()["type"] == "script"
    # outline unchanged
    objs = client.get(f"/api/v1/projects/{p['id']}/creative-objects").json()
    assert any(o["id"] == outline_id for o in objs)
    # Status now writing
    proj = client.get(f"/api/v1/projects/{p['id']}").json()
    assert proj["status"] == "writing"


def test_content_type_maps_to_creative_type(client, cleandb):
    mapping = {
        "youtube_video": "script",
        "instagram_reel": "script",
        "instagram_post": "caption",
        "instagram_carousel": "carousel",
    }
    for ct, out_type in mapping.items():
        p = _create_project(client, content_type=ct)
        r = client.post(f"/api/v1/projects/{p['id']}/ai/content")
        assert r.status_code == 200, ct
        assert r.json()["type"] == out_type, f"{ct} → {r.json()['type']}"


# ============================================================
# Edit / Critique — never overwrite
# ============================================================
def test_edit_returns_proposal_without_mutation(client, cleandb):
    p = _create_project(client)
    # Create a manual creative object
    obj = client.post(f"/api/v1/projects/{p['id']}/creative-objects", json={
        "type": "script", "title": "T", "content": "ORIGINAL CONTENT",
    }).json()
    _Fake.edit_out = "PROPOSED REWRITE"
    r = client.post(f"/api/v1/projects/{p['id']}/ai/edit", json={
        "action": "rewrite", "content": obj["content"], "instruction": "Punchier",
    })
    assert r.status_code == 200
    assert r.json()["proposal"] == "PROPOSED REWRITE"
    # DB object is untouched
    fresh = client.get(f"/api/v1/projects/{p['id']}/creative-objects").json()
    matched = next(o for o in fresh if o["id"] == obj["id"])
    assert matched["content"] == "ORIGINAL CONTENT"


def test_improve_hook_and_critique(client, cleandb):
    p = _create_project(client)
    _Fake.edit_out = "IMPROVED FULL CONTENT"
    r = client.post(f"/api/v1/projects/{p['id']}/ai/edit", json={
        "action": "improve_hook", "content": "Original content here.",
    })
    assert r.status_code == 200
    assert r.json()["proposal"] == "IMPROVED FULL CONTENT"

    r = client.post(f"/api/v1/projects/{p['id']}/ai/edit", json={
        "action": "critique", "content": "Text",
    })
    assert r.status_code == 200
    assert "strengths" in r.json()["critique"]

    r = client.post(f"/api/v1/projects/{p['id']}/ai/edit", json={
        "action": "unknown", "content": "Text",
    })
    assert r.status_code == 400


def test_edit_failure_leaves_content_intact(client, cleandb):
    p = _create_project(client)
    obj = client.post(f"/api/v1/projects/{p['id']}/creative-objects", json={
        "type": "script", "content": "STAYS",
    }).json()
    _Fake.fail = "edit"
    r = client.post(f"/api/v1/projects/{p['id']}/ai/edit", json={
        "action": "rewrite", "content": obj["content"],
    })
    assert r.status_code == 502
    fresh = client.get(f"/api/v1/projects/{p['id']}/creative-objects").json()
    assert next(o for o in fresh if o["id"] == obj["id"])["content"] == "STAYS"


# ============================================================
# Chat
# ============================================================
def test_chat_persists_both_turns(client, cleandb):
    p = _create_project(client)
    r = client.post(f"/api/v1/projects/{p['id']}/ai/chat", json={"message": "What angle should I take?"})
    assert r.status_code == 200
    hist = client.get(f"/api/v1/projects/{p['id']}/ai/chat").json()
    roles = [m["role"] for m in hist]
    assert roles == ["user", "assistant"]
    assert hist[0]["content"] == "What angle should I take?"
    assert hist[1]["content"]  # assistant reply present


def test_chat_persists_user_turn_even_when_ai_fails(client, cleandb):
    p = _create_project(client)
    _Fake.fail = "chat"
    r = client.post(f"/api/v1/projects/{p['id']}/ai/chat", json={"message": "Q"})
    assert r.status_code == 502
    hist = client.get(f"/api/v1/projects/{p['id']}/ai/chat").json()
    # user turn preserved; assistant error marker persisted
    assert hist[0]["role"] == "user" and hist[0]["content"] == "Q"
    assert hist[-1]["role"] == "assistant"
    assert "unavailable" in hist[-1]["content"].lower()


# ============================================================
# Ownership isolation on M3 endpoints
# ============================================================
def test_ownership_isolation_on_all_m3_endpoints(client, cleandb):
    from datetime import datetime, timezone
    pid = "iso-" + uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    cleandb.projects.insert_one({
        "id": pid, "creator_id": "other-creator", "workspace_id": "other-ws",
        "title": "Not yours", "content_type": "youtube_video", "platform": "youtube",
        "objective": None, "status": "idea",
        "brief": {"topic": None, "objective": None, "target_audience": None,
                  "content_format": None, "takeaway": None, "working_title": None},
        "created_at": now, "updated_at": now,
    })
    # every M3 endpoint must 404
    for method, path, body in [
        ("GET",  f"/api/v1/projects/{pid}/sources", None),
        ("POST", f"/api/v1/projects/{pid}/sources", {"title": "x", "source_type": "text", "content": "x"}),
        ("DELETE", f"/api/v1/projects/{pid}/sources/none", None),
        ("POST", f"/api/v1/projects/{pid}/ai/research", {"question": "q"}),
        ("POST", f"/api/v1/projects/{pid}/ai/directions", {}),
        ("PUT",  f"/api/v1/projects/{pid}/ai/direction/selected", {"angle": "a"}),
        ("POST", f"/api/v1/projects/{pid}/ai/outline", {}),
        ("POST", f"/api/v1/projects/{pid}/ai/content", {}),
        ("POST", f"/api/v1/projects/{pid}/ai/edit", {"action": "rewrite", "content": "x"}),
        ("GET",  f"/api/v1/projects/{pid}/ai/chat", None),
        ("POST", f"/api/v1/projects/{pid}/ai/chat", {"message": "hi"}),
    ]:
        if method == "GET":
            r = client.get(path)
        elif method == "POST":
            r = client.post(path, json=body or {})
        elif method == "PUT":
            r = client.put(path, json=body or {})
        elif method == "DELETE":
            r = client.delete(path)
        assert r.status_code == 404, f"{method} {path} should 404 but got {r.status_code}"
