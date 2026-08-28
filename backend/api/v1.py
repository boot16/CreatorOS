"""Production v1 API — authenticated identity + workspace-scoped operations."""
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, BackgroundTasks

from core.config import get_settings
from core.errors import AppError, Codes
from core.identity import CurrentUser, SESSION_COOKIE, resolve_identity, require_real_auth, require_creator
from core.rate_limit import get_rate_limiter, BUDGETS
from api.schemas import (
    CurrentCreatorContext, CreatorIntentBody, CreatorIntentResponse,
    SyncResultResponse, CreatorDNAResponse, DNAComputeResponse, ConnectedPlatformResponse,
)
from repositories import IntentRepo, DNARepo, PlatformRepo, CreatorRepo
from models.domain import CreatorDNASnapshot, DNAStatus
from services.creator_dna import (CreatorDNAService, DNA_PIPELINE_VERSION,
                                  VIDEO_ANALYSIS_PROMPT_VERSION, VIDEO_ANALYSIS_MODEL)
from services.youtube_sync import YouTubeSyncService
from providers import make_creator_provider


def build_v1_router(db):
    router = APIRouter(prefix="/v1", tags=["v1"])

    async def _user_dep(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)) -> CurrentUser:
        return await resolve_identity(db, sid)

    @router.get("/me", response_model=CurrentCreatorContext)
    async def me(user: CurrentUser = Depends(_user_dep)):
        """Single bootstrap endpoint — frontend calls once on load."""
        settings = get_settings()
        creator_provider = make_creator_provider(db)
        creator = await creator_provider.get_current_creator(user)

        dna = None
        yt_connected = False
        yt_last_synced_at = None
        if user.creator_id and user.is_authenticated:
            dna = await DNARepo(db).latest(user.creator_id)
            yt_platform = await PlatformRepo(db).get_for_creator(user.creator_id, "youtube")
            yt_connected = yt_platform is not None
            yt_last_synced_at = yt_platform.last_synced_at if yt_platform else None
        dna_status = dna.status.value if dna else "not_computed"

        return CurrentCreatorContext(
            is_authenticated=user.is_authenticated,
            is_demo=user.is_demo,
            data_mode=settings.DATA_MODE,
            user=({"id": user.user_id, "email": user.email, "name": user.name}
                   if (user.is_authenticated or user.is_demo) else None),
            creator=(creator if creator else None),
            workspace=({"id": user.workspace_id} if user.workspace_id else None),
            youtube_connected=yt_connected,
            youtube_last_synced_at=yt_last_synced_at,
            dna_status=dna_status,
        )

    @router.get("/creator-intent", response_model=CreatorIntentResponse)
    async def get_intent(user: CurrentUser = Depends(_user_dep)):
        require_real_auth(user)
        creator_id = require_creator(user)
        intent = await IntentRepo(db).get(creator_id)
        if not intent:
            return CreatorIntentResponse(creator_id=creator_id)
        return CreatorIntentResponse(**intent.model_dump())

    @router.put("/creator-intent", response_model=CreatorIntentResponse)
    async def save_intent(body: CreatorIntentBody, user: CurrentUser = Depends(_user_dep)):
        require_real_auth(user)
        creator_id = require_creator(user)
        get_rate_limiter().check(f"intent-{user.user_id}", 20, 60)
        patch = body.model_dump(exclude_none=True)
        intent = await IntentRepo(db).upsert(creator_id, patch)
        return CreatorIntentResponse(**intent.model_dump())

    @router.post("/sync/youtube", response_model=SyncResultResponse)
    async def sync_youtube(user: CurrentUser = Depends(_user_dep)):
        require_real_auth(user)
        creator_id = require_creator(user)
        get_rate_limiter().check(f"sync-{user.user_id}", 5, 300)  # 5 syncs per 5 min
        result = await YouTubeSyncService(db).sync(creator_id)
        return SyncResultResponse(**result)

    @router.get("/dna", response_model=CreatorDNAResponse)
    async def dna_status(user: CurrentUser = Depends(_user_dep)):
        require_real_auth(user)
        creator_id = require_creator(user)
        dna = await DNARepo(db).latest(creator_id)
        if not dna:
            return CreatorDNAResponse(creator_id=creator_id, status="not_computed")
        payload = dna.model_dump()
        payload.pop("id", None); payload.pop("created_at", None); payload.pop("source_snapshot_ids", None); payload.pop("model_versions", None)
        payload["status"] = {"ready": "computed", "error": "failed"}.get(dna.status.value, dna.status.value)
        return CreatorDNAResponse(**payload)

    async def _compute_in_background(creator_id: str):
        try:
            await CreatorDNAService(db).compute_creator_dna(creator_id)
        except Exception:
            # The client retains a truthful terminal state and can safely retry.
            repo = DNARepo(db)
            await repo.create(CreatorDNASnapshot(
                creator_id=creator_id, version=await repo.next_version(creator_id), status=DNAStatus.failed,
                computed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                pipeline_version="1.0", computation_metadata={"failure": "computation failed safely; retry after sync"},
            ))

    @router.post("/dna/compute", response_model=DNAComputeResponse, status_code=202)
    async def compute_dna(background_tasks: BackgroundTasks, user: CurrentUser = Depends(_user_dep)):
        require_real_auth(user)
        creator_id = require_creator(user)
        repo = DNARepo(db)
        latest = await repo.latest(creator_id)
        if latest and latest.status == DNAStatus.computing:
            return DNAComputeResponse(status="computing", accepted=True, message="Creator DNA computation is already running.")
        fingerprint = await CreatorDNAService(db).current_source_fingerprint(creator_id)
        equivalent = await repo.equivalent(creator_id, fingerprint, DNA_PIPELINE_VERSION,
                                           VIDEO_ANALYSIS_PROMPT_VERSION, [VIDEO_ANALYSIS_MODEL])
        if equivalent:
            return DNAComputeResponse(status=equivalent.status.value, accepted=False,
                                      message="Current source data is already analyzed.")
        # FastAPI BackgroundTasks is intentionally bounded by the service's three concurrent LLM calls.
        # A persistent job queue is the production scaling follow-up, not a hidden synchronous browser wait.
        await repo.create(CreatorDNASnapshot(creator_id=creator_id, version=await repo.next_version(creator_id),
                                             status=DNAStatus.computing, computed_at=None,
                                             pipeline_version="1.0"))
        background_tasks.add_task(_compute_in_background, creator_id)
        return DNAComputeResponse(status="computing", accepted=True, message="Creator DNA computation started.")

    @router.get("/platforms")
    async def list_platforms(user: CurrentUser = Depends(_user_dep)):
        require_real_auth(user)
        creator_id = require_creator(user)
        items = await PlatformRepo(db).list_for_creator(creator_id)
        return [ConnectedPlatformResponse(
            id=cp.id, platform=cp.platform.value if hasattr(cp.platform, "value") else cp.platform,
            display_name=cp.display_name, handle=cp.handle,
            connection_status=cp.connection_status.value if hasattr(cp.connection_status, "value") else cp.connection_status,
            last_synced_at=cp.last_synced_at,
        ) for cp in items]

    return router
