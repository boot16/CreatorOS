"""M1 regression tests — session ownership + health endpoint + token refresh helper."""
import os, sys, asyncio, uuid
sys.path.insert(0, '/app/backend')
os.environ.setdefault('MONGO_URL', 'mongodb://localhost:27017')
os.environ.setdefault('DB_NAME', 'test_database_m1')
os.environ.setdefault('EMERGENT_LLM_KEY', 'x')
os.environ.setdefault('APP_ENCRYPTION_KEY', 'Ah8FVpGr9tYq6cV2s7bH3nD1kX0mLpQeR4uJ_wZcYvA=')

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from services.youtube_tokens import refresh_access_token


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    d = client['test_m1_' + uuid.uuid4().hex[:6]]
    yield d
    await client.drop_database(d.name)


@pytest.mark.asyncio
async def test_health_endpoint_shape():
    """Health endpoint returns predictable JSON — used by deployment probes."""
    from fastapi.testclient import TestClient
    # server.py imports load .env at module time — safe to reuse
    from server import app
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "CreatorOS"


@pytest.mark.asyncio
async def test_refresh_returns_none_when_no_refresh_token(db):
    """No stored refresh_token → returns None (caller keeps existing behavior)."""
    # Create a platform + credential with only access_token
    from repositories import CredentialRepo, PlatformRepo, CreatorRepo
    from models.domain import PlatformCredential
    from core.encryption import encrypt
    creator = await CreatorRepo(db).upsert_for_user("u-m1", "w-m1", {"display_name": "C"})
    cp = await PlatformRepo(db).upsert(creator.id, "youtube", "gs-1", {
        "external_channel_id": "UC1", "connection_status": "connected",
    })
    await CredentialRepo(db).upsert(cp.id, PlatformCredential(
        connected_platform_id=cp.id,
        encrypted_access_token=encrypt("stale"),
        encrypted_refresh_token=None,
    ))
    got = await refresh_access_token(db, cp.id)
    assert got is None


@pytest.mark.asyncio
async def test_refresh_returns_none_when_google_unconfigured(db, monkeypatch):
    """No GOOGLE_CLIENT_ID → returns None instead of crashing."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    from core.config import get_settings
    get_settings.cache_clear()
    from repositories import CredentialRepo, PlatformRepo, CreatorRepo
    from models.domain import PlatformCredential
    from core.encryption import encrypt
    creator = await CreatorRepo(db).upsert_for_user("u-m1b", "w-m1b", {"display_name": "C"})
    cp = await PlatformRepo(db).upsert(creator.id, "youtube", "gs-2", {"connection_status": "connected"})
    await CredentialRepo(db).upsert(cp.id, PlatformCredential(
        connected_platform_id=cp.id,
        encrypted_access_token=encrypt("stale"),
        encrypted_refresh_token=encrypt("refresh-token"),
    ))
    got = await refresh_access_token(db, cp.id)
    assert got is None
