"""Phase 1 foundation tests — identity, providers, ownership, sync, cache."""
import os, sys, asyncio, uuid
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database_phase1')
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('LLM_PROVIDER', 'anthropic')
os.environ.setdefault('LLM_MODEL', 'claude-sonnet-4-6')
os.environ.setdefault('APP_ENCRYPTION_KEY', 'Ah8FVpGr9tYq6cV2s7bH3nD1kX0mLpQeR4uJ_wZcYvA=')

sys.path.insert(0, '/app/backend')

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta

from core.config import get_settings
from core.identity import CurrentUser, resolve_identity, DEMO_CREATOR_ID
from core.encryption import encrypt, decrypt
from core.rate_limit import RateLimiter
from core.errors import AppError, Codes
from repositories import (
    UserRepo, WorkspaceRepo, CreatorRepo, PlatformRepo, CredentialRepo,
    YouTubeSourceRepo, IntentRepo, DNARepo, SessionRepo, LLMCacheRepo,
)
from models.domain import CreatorVideo, PlatformCredential, LLMCacheEntry
from providers import DemoCreatorProvider, DemoOpportunityProvider


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    d = client['test_phase1_' + uuid.uuid4().hex[:6]]
    yield d
    await client.drop_database(d.name)


# ---------- identity ----------
@pytest.mark.asyncio
async def test_resolve_identity_demo_returns_alex(db, monkeypatch):
    monkeypatch.setenv("DATA_MODE", "demo")
    get_settings.cache_clear()
    user = await resolve_identity(db, sid=None)
    assert user.is_demo is True
    assert user.creator_id == DEMO_CREATOR_ID
    assert user.is_authenticated is False


@pytest.mark.asyncio
async def test_resolve_identity_production_no_session(db, monkeypatch):
    monkeypatch.setenv("DATA_MODE", "production")
    get_settings.cache_clear()
    user = await resolve_identity(db, sid=None)
    assert user.is_demo is False
    assert user.is_authenticated is False
    assert user.creator_id is None
    assert user.workspace_id is None


@pytest.mark.asyncio
async def test_expired_session_is_rejected(db, monkeypatch):
    monkeypatch.setenv("DATA_MODE", "production")
    get_settings.cache_clear()
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await db.sessions.insert_one({"sid": "expired-sid", "user_id": "u1", "expires_at": past})
    user = await resolve_identity(db, sid="expired-sid")
    assert user.is_authenticated is False


# ---------- ownership ----------
@pytest.mark.asyncio
async def test_workspaces_are_owned_and_isolated(db):
    ws_repo = WorkspaceRepo(db)
    ws1 = await ws_repo.create_owner_workspace("user-A", "A")
    ws2 = await ws_repo.create_owner_workspace("user-B", "B")
    assert ws1.owner_user_id == "user-A"
    assert ws2.owner_user_id == "user-B"
    assert ws1.id != ws2.id
    assert await ws_repo.user_can_access(ws1.id, "user-A") is True
    assert await ws_repo.user_can_access(ws1.id, "user-B") is False


@pytest.mark.asyncio
async def test_creator_belongs_to_one_workspace(db):
    creator_repo = CreatorRepo(db)
    c = await creator_repo.upsert_for_user("user-A", "ws-A", {"display_name": "A"})
    # Second call updates, does not duplicate
    c2 = await creator_repo.upsert_for_user("user-A", "ws-A", {"display_name": "A prime"})
    assert c.id == c2.id
    count = await db.creators.count_documents({"user_id": "user-A"})
    assert count == 1


@pytest.mark.asyncio
async def test_production_provider_isolates_by_workspace(db, monkeypatch):
    monkeypatch.setenv("DATA_MODE", "production")
    get_settings.cache_clear()
    from providers import ProductionCreatorProvider
    prov = ProductionCreatorProvider(CreatorRepo(db), YouTubeSourceRepo(db))
    c = await (CreatorRepo(db).upsert_for_user("user-A", "ws-A", {"display_name": "Alice"}))
    # Same-workspace requester → gets creator
    same_ws = CurrentUser(user_id="user-A", creator_id=c.id, workspace_id="ws-A",
                           is_authenticated=True, is_demo=False)
    got = await prov.get_creator(c.id, same_ws)
    assert got is not None
    # Different-workspace requester → None (no leakage)
    other_ws = CurrentUser(user_id="user-B", creator_id=None, workspace_id="ws-OTHER",
                            is_authenticated=True, is_demo=False)
    leaked = await prov.get_creator(c.id, other_ws)
    assert leaked is None


# ---------- demo isolation ----------
@pytest.mark.asyncio
async def test_demo_provider_returns_alex():
    prov = DemoCreatorProvider()
    user = CurrentUser(user_id="demo", creator_id=DEMO_CREATOR_ID, workspace_id="w",
                       is_authenticated=False, is_demo=True)
    c = await prov.get_current_creator(user)
    assert c is not None
    assert c["id"] == "alex-morgan"
    assert len(c["pillars"]) == 5


@pytest.mark.asyncio
async def test_production_provider_does_not_return_alex(db, monkeypatch):
    monkeypatch.setenv("DATA_MODE", "production")
    get_settings.cache_clear()
    from providers import ProductionCreatorProvider, ProductionOpportunityProvider, ProductionTrendProvider
    cp = ProductionCreatorProvider(CreatorRepo(db), YouTubeSourceRepo(db))
    op = ProductionOpportunityProvider()
    tp = ProductionTrendProvider()
    user = CurrentUser(user_id="anon", creator_id=None, workspace_id=None,
                       is_authenticated=False, is_demo=False)
    assert await cp.get_current_creator(user) is None
    assert await cp.get_creator("alex-morgan", user) is None
    opps = await op.list_for_creator(user)
    assert opps["status"] == "not_computed"
    assert opps["items"] == []
    trends = await tp.list_trends()
    assert trends["status"] == "not_computed"


# ---------- intent ----------
@pytest.mark.asyncio
async def test_intent_upsert_and_load(db):
    repo = IntentRepo(db)
    await repo.upsert("creator-1", {"primary_goal": "grow", "desired_topics": ["ai"]})
    got = await repo.get("creator-1")
    assert got is not None
    assert got.primary_goal == "grow"
    assert got.desired_topics == ["ai"]
    await repo.upsert("creator-1", {"primary_goal": "monetize"})
    updated = await repo.get("creator-1")
    assert updated.primary_goal == "monetize"
    assert updated.desired_topics == ["ai"]  # not lost


@pytest.mark.asyncio
async def test_intent_ownership_isolation(db):
    repo = IntentRepo(db)
    await repo.upsert("creator-A", {"primary_goal": "A"})
    await repo.upsert("creator-B", {"primary_goal": "B"})
    a = await repo.get("creator-A")
    b = await repo.get("creator-B")
    assert a.primary_goal == "A" and b.primary_goal == "B"


# ---------- YouTube sync idempotency ----------
class _FakeHttp:
    """Stub httpx.AsyncClient. Not context-manager-used by service (we pass it directly)."""
    def __init__(self, responses):
        self.responses = responses
    async def get(self, url, params=None, headers=None):
        for pattern, resp in self.responses.items():
            if pattern in url:
                return resp
        raise RuntimeError(f"No stub for {url}")
    async def aclose(self):
        pass


class _Resp:
    def __init__(self, code, data): self.status_code = code; self._data = data
    def json(self): return self._data


@pytest.mark.asyncio
async def test_youtube_sync_idempotent(db):
    from services.youtube_sync import YouTubeSyncService
    # Set up creator + platform + credential
    creator = await CreatorRepo(db).upsert_for_user("u", "w", {"display_name": "C"})
    cp = await PlatformRepo(db).upsert(creator.id, "youtube", "goog-sub-1", {
        "external_channel_id": "UC1", "display_name": "C", "connection_status": "connected",
    })
    await CredentialRepo(db).upsert(cp.id, PlatformCredential(
        connected_platform_id=cp.id,
        encrypted_access_token=encrypt("access-token"),
        scopes=["youtube.readonly"],
    ))

    responses = {
        "youtube/v3/channels": _Resp(200, {"items": [{
            "id": "UC1", "snippet": {"title": "C", "description": ""},
            "statistics": {"subscriberCount": "1000", "viewCount": "100000", "videoCount": "2"},
            "contentDetails": {"relatedPlaylists": {"uploads": "PL1"}},
        }]}),
        "playlistItems": _Resp(200, {"items": [
            {"contentDetails": {"videoId": "v1"}},
            {"contentDetails": {"videoId": "v2"}},
        ]}),
        "youtube/v3/videos": _Resp(200, {"items": [
            {"id": "v1", "snippet": {"title": "T1", "publishedAt": "2026-01-01T00:00:00Z",
                                       "thumbnails": {"medium": {"url": "http://x/1.jpg"}}},
             "statistics": {"viewCount": "500"}},
            {"id": "v2", "snippet": {"title": "T2", "publishedAt": "2026-01-02T00:00:00Z",
                                       "thumbnails": {"medium": {"url": "http://x/2.jpg"}}},
             "statistics": {"viewCount": "700"}},
        ]}),
    }
    fake = _FakeHttp(responses)
    svc = YouTubeSyncService(db, http_client=fake)

    # First sync: creates 2 videos
    r1 = await svc.sync(creator.id)
    assert r1["videos_created"] == 2
    assert r1["videos_updated"] == 0
    assert r1["videos_seen"] == 2

    # Second sync: same data — 0 created, 2 updated (idempotent, no dupes)
    r2 = await svc.sync(creator.id)
    assert r2["videos_created"] == 0
    assert r2["videos_updated"] == 2
    count = await db.creator_videos.count_documents({"creator_id": creator.id})
    assert count == 2  # not 4


@pytest.mark.asyncio
async def test_youtube_sync_requires_connection(db):
    from services.youtube_sync import YouTubeSyncService
    creator = await CreatorRepo(db).upsert_for_user("u2", "w2", {"display_name": "C2"})
    svc = YouTubeSyncService(db)
    with pytest.raises(AppError) as exc:
        await svc.sync(creator.id)
    assert exc.value.code == Codes.YOUTUBE_NOT_CONNECTED


# ---------- LLM cache versioning ----------
@pytest.mark.asyncio
async def test_llm_cache_data_version_mismatch(db):
    repo = LLMCacheRepo(db)
    k1 = repo.compute_key("idea_lab", "opp-1", 1, 1, 1, "anthropic/claude-sonnet-4-6")
    k2 = repo.compute_key("idea_lab", "opp-1", 1, 2, 1, "anthropic/claude-sonnet-4-6")  # bumped data_version
    assert k1 != k2
    await repo.put(LLMCacheEntry(cache_kind="idea_lab", entity_id="opp-1", data_version=1,
                                    prompt_version=1, model="anthropic/claude-sonnet-4-6",
                                    key_hash=k1, value={"titles": ["A"]}))
    assert await repo.get(k1) == {"titles": ["A"]}
    # New data version => cache miss
    assert await repo.get(k2) is None


# ---------- encryption ----------
def test_encryption_roundtrip():
    ct = encrypt("secret-token")
    assert ct != "secret-token"
    assert decrypt(ct) == "secret-token"


# ---------- rate limit ----------
def test_rate_limiter_blocks_after_limit():
    rl = RateLimiter()
    for _ in range(3):
        rl.check("k", 3, 60)
    with pytest.raises(AppError) as exc:
        rl.check("k", 3, 60)
    assert exc.value.code == Codes.RATE_LIMITED


# ---------- ownership: caller cannot override identity ----------
@pytest.mark.asyncio
async def test_caller_cannot_override_identity_via_shortlist(db, monkeypatch):
    """POST /shortlist under two different sessions should be isolated even
    if both callers send the same X-Client-Id. Because we key by resolved user_id
    when authenticated, one session's items must not appear for another session.
    This is asserted at the repo/logic level here (integration-level).
    """
    monkeypatch.setenv("DATA_MODE", "production")
    get_settings.cache_clear()
    # Simulate two authenticated users
    u1 = CurrentUser(user_id="U1", creator_id=None, workspace_id=None,
                     is_authenticated=True, is_demo=False)
    u2 = CurrentUser(user_id="U2", creator_id=None, workspace_id=None,
                     is_authenticated=True, is_demo=False)
    from server import _owner_key  # type: ignore
    k1 = _owner_key(u1, "same-client-id")
    k2 = _owner_key(u2, "same-client-id")
    assert k1 != k2  # identity-based, not client-supplied
