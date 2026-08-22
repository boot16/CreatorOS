"""Repository layer — the ONLY place that touches Mongo directly.

Business rules and API handlers should never call db.<collection> directly.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import hashlib

from motor.motor_asyncio import AsyncIOMotorDatabase

from models.domain import (
    User, Workspace, WorkspaceMember, Creator, ConnectedPlatform, PlatformCredential,
    YouTubeChannelSnapshot, CreatorVideo, VideoMetricSnapshot,
    CreatorIntent, CreatorDNASnapshot, Session, LLMCacheEntry,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserRepo:
    def __init__(self, db): self.db = db
    async def upsert_by_google_sub(self, sub: str, patch: dict) -> User:
        doc = await self.db.users.find_one({"google_sub": sub}, {"_id": 0})
        if doc:
            patch["updated_at"] = _now()
            await self.db.users.update_one({"google_sub": sub}, {"$set": patch})
            doc.update(patch)
            return User(**doc)
        user = User(google_sub=sub, **patch)
        await self.db.users.insert_one(user.model_dump())
        return user
    async def get(self, user_id: str) -> Optional[User]:
        doc = await self.db.users.find_one({"id": user_id}, {"_id": 0})
        return User(**doc) if doc else None


class WorkspaceRepo:
    def __init__(self, db): self.db = db
    async def create_owner_workspace(self, user_id: str, name: str) -> Workspace:
        existing = await self.db.workspaces.find_one({"owner_user_id": user_id}, {"_id": 0})
        if existing:
            return Workspace(**existing)
        slug_base = (name or "workspace").lower().replace(" ", "-")[:32] + "-" + user_id[:6]
        ws = Workspace(owner_user_id=user_id, name=name or "Workspace", slug=slug_base)
        await self.db.workspaces.insert_one(ws.model_dump())
        await self.db.workspace_members.insert_one(
            WorkspaceMember(workspace_id=ws.id, user_id=user_id, role="owner").model_dump()
        )
        return ws
    async def get_by_owner(self, user_id: str) -> Optional[Workspace]:
        doc = await self.db.workspaces.find_one({"owner_user_id": user_id}, {"_id": 0})
        return Workspace(**doc) if doc else None
    async def user_can_access(self, workspace_id: str, user_id: str) -> bool:
        m = await self.db.workspace_members.find_one({"workspace_id": workspace_id, "user_id": user_id, "status": "active"})
        return m is not None


class CreatorRepo:
    def __init__(self, db): self.db = db
    async def upsert_for_user(self, user_id: str, workspace_id: str, patch: dict) -> Creator:
        existing = await self.db.creators.find_one({"user_id": user_id}, {"_id": 0})
        if existing:
            patch["updated_at"] = _now()
            await self.db.creators.update_one({"user_id": user_id}, {"$set": patch})
            existing.update(patch)
            return Creator(**existing)
        c = Creator(user_id=user_id, workspace_id=workspace_id, **patch)
        await self.db.creators.insert_one(c.model_dump())
        return c
    async def get(self, creator_id: str) -> Optional[Creator]:
        doc = await self.db.creators.find_one({"id": creator_id}, {"_id": 0})
        return Creator(**doc) if doc else None
    async def get_by_user(self, user_id: str) -> Optional[Creator]:
        doc = await self.db.creators.find_one({"user_id": user_id}, {"_id": 0})
        return Creator(**doc) if doc else None


class PlatformRepo:
    def __init__(self, db): self.db = db
    async def upsert(self, creator_id: str, platform: str, external_account_id: str, patch: dict) -> ConnectedPlatform:
        q = {"creator_id": creator_id, "platform": platform, "external_account_id": external_account_id}
        existing = await self.db.connected_platforms.find_one(q, {"_id": 0})
        if existing:
            patch["updated_at"] = _now()
            await self.db.connected_platforms.update_one(q, {"$set": patch})
            existing.update(patch)
            return ConnectedPlatform(**existing)
        cp = ConnectedPlatform(creator_id=creator_id, platform=platform, external_account_id=external_account_id, **patch)
        await self.db.connected_platforms.insert_one(cp.model_dump())
        return cp
    async def get_for_creator(self, creator_id: str, platform: str) -> Optional[ConnectedPlatform]:
        doc = await self.db.connected_platforms.find_one({"creator_id": creator_id, "platform": platform}, {"_id": 0})
        return ConnectedPlatform(**doc) if doc else None
    async def list_for_creator(self, creator_id: str) -> List[ConnectedPlatform]:
        cursor = self.db.connected_platforms.find({"creator_id": creator_id}, {"_id": 0})
        return [ConnectedPlatform(**d) async for d in cursor]
    async def mark_synced(self, cp_id: str):
        await self.db.connected_platforms.update_one({"id": cp_id}, {"$set": {"last_synced_at": _now(), "updated_at": _now()}})


class CredentialRepo:
    def __init__(self, db): self.db = db
    async def upsert(self, connected_platform_id: str, cred: PlatformCredential):
        cred.updated_at = _now()
        await self.db.platform_credentials.update_one(
            {"connected_platform_id": connected_platform_id},
            {"$set": cred.model_dump()},
            upsert=True,
        )
    async def get(self, connected_platform_id: str) -> Optional[PlatformCredential]:
        doc = await self.db.platform_credentials.find_one({"connected_platform_id": connected_platform_id}, {"_id": 0})
        return PlatformCredential(**doc) if doc else None


class YouTubeSourceRepo:
    def __init__(self, db): self.db = db
    async def add_channel_snapshot(self, snap: YouTubeChannelSnapshot):
        await self.db.youtube_channel_snapshots.insert_one(snap.model_dump())
    async def latest_channel_snapshot(self, creator_id: str) -> Optional[YouTubeChannelSnapshot]:
        doc = await self.db.youtube_channel_snapshots.find_one(
            {"creator_id": creator_id}, {"_id": 0}, sort=[("captured_at", -1)]
        )
        return YouTubeChannelSnapshot(**doc) if doc else None
    async def upsert_video(self, video: CreatorVideo) -> tuple[CreatorVideo, bool]:
        """Returns (video, created)"""
        q = {"creator_id": video.creator_id, "external_video_id": video.external_video_id}
        existing = await self.db.creator_videos.find_one(q, {"_id": 0})
        if existing:
            patch = video.model_dump()
            patch.pop("id", None); patch.pop("created_at", None)
            patch["updated_at"] = _now()
            await self.db.creator_videos.update_one(q, {"$set": patch})
            existing.update(patch)
            return CreatorVideo(**existing), False
        await self.db.creator_videos.insert_one(video.model_dump())
        return video, True
    async def add_metric_snapshot(self, snap: VideoMetricSnapshot):
        await self.db.video_metric_snapshots.insert_one(snap.model_dump())
    async def list_videos(self, creator_id: str, limit: int = 20) -> List[CreatorVideo]:
        cursor = self.db.creator_videos.find({"creator_id": creator_id}, {"_id": 0}).sort("published_at", -1).limit(limit)
        return [CreatorVideo(**d) async for d in cursor]


class IntentRepo:
    def __init__(self, db): self.db = db
    async def get(self, creator_id: str) -> Optional[CreatorIntent]:
        doc = await self.db.creator_intent.find_one({"creator_id": creator_id}, {"_id": 0})
        return CreatorIntent(**doc) if doc else None
    async def upsert(self, creator_id: str, patch: dict) -> CreatorIntent:
        existing = await self.db.creator_intent.find_one({"creator_id": creator_id}, {"_id": 0})
        if existing:
            patch["updated_at"] = _now()
            await self.db.creator_intent.update_one({"creator_id": creator_id}, {"$set": patch})
            existing.update(patch)
            return CreatorIntent(**existing)
        intent = CreatorIntent(creator_id=creator_id, **patch)
        await self.db.creator_intent.insert_one(intent.model_dump())
        return intent


class DNARepo:
    def __init__(self, db): self.db = db
    async def latest(self, creator_id: str) -> Optional[CreatorDNASnapshot]:
        doc = await self.db.creator_dna_snapshots.find_one(
            {"creator_id": creator_id}, {"_id": 0}, sort=[("computed_at", -1)]
        )
        return CreatorDNASnapshot(**doc) if doc else None
    async def get_or_create_placeholder(self, creator_id: str) -> CreatorDNASnapshot:
        existing = await self.latest(creator_id)
        if existing:
            return existing
        snap = CreatorDNASnapshot(creator_id=creator_id)
        await self.db.creator_dna_snapshots.insert_one(snap.model_dump())
        return snap


class SessionRepo:
    def __init__(self, db, max_age_seconds: int = 2592000):
        self.db = db
        self.max_age = max_age_seconds
    async def create(self, sid: str, user_id: str, email: Optional[str], name: Optional[str]) -> Session:
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=self.max_age)).isoformat()
        sess = Session(sid=sid, user_id=user_id, email=email, name=name, expires_at=expires_at)
        await self.db.sessions.insert_one(sess.model_dump())
        return sess
    async def revoke(self, sid: str):
        await self.db.sessions.delete_one({"sid": sid})


class LLMCacheRepo:
    def __init__(self, db): self.db = db
    @staticmethod
    def compute_key(cache_kind: str, entity_id: str, entity_version: int,
                     data_version: int, prompt_version: int, model: str) -> str:
        raw = f"{cache_kind}|{entity_id}|{entity_version}|{data_version}|{prompt_version}|{model}"
        return hashlib.sha256(raw.encode()).hexdigest()
    async def get(self, key_hash: str):
        doc = await self.db.llm_cache_v2.find_one({"key_hash": key_hash}, {"_id": 0})
        if not doc:
            return None
        if doc.get("expires_at") and datetime.fromisoformat(doc["expires_at"]) < datetime.now(timezone.utc):
            return None
        return doc.get("value")
    async def put(self, entry: LLMCacheEntry):
        await self.db.llm_cache_v2.update_one(
            {"key_hash": entry.key_hash}, {"$set": entry.model_dump()}, upsert=True,
        )
    async def bust(self, cache_kind: str, entity_id: str):
        await self.db.llm_cache_v2.delete_many({"cache_kind": cache_kind, "entity_id": entity_id})
