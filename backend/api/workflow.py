"""M5 workflow architecture: living foundation + learning signals."""
from typing import Optional, Any

from fastapi import APIRouter, Cookie, Depends
from pydantic import BaseModel, Field

from core.errors import AppError, Codes
from core.identity import CurrentUser, SESSION_COOKIE, resolve_identity
from models.m5 import FoundationField, LearningSignal
from repositories import ProjectRepo, ActivityEventRepo
from repositories.project_foundation import ProjectFoundationRepo
from repositories.learning import LearningSignalRepo, PreferenceEvidenceRepo
from services.project_foundation import build_project_foundation


class FoundationInput(BaseModel):
    message: str = Field(min_length=2, max_length=10000)


class FoundationPatch(BaseModel):
    vision: Optional[str] = Field(default=None, max_length=4000)
    context: Optional[str] = Field(default=None, max_length=6000)
    goal: Optional[str] = Field(default=None, max_length=3000)
    audience: Optional[str] = Field(default=None, max_length=3000)
    creator_perspective: Optional[str] = Field(default=None, max_length=4000)
    platform_format: Optional[str] = Field(default=None, max_length=1000)
    constraints: Optional[list[str]] = Field(default=None, max_length=10)
    known_facts: Optional[list[str]] = Field(default=None, max_length=15)
    material_unknowns: Optional[list[str]] = Field(default=None, max_length=8)
    decisions: Optional[list[str]] = Field(default=None, max_length=20)


class SignalInput(BaseModel):
    signal_type: str = Field(min_length=2, max_length=100)
    target_type: Optional[str] = Field(default=None, max_length=100)
    target_id: Optional[str] = Field(default=None, max_length=200)
    strength: str = "medium"
    payload: dict[str, Any] = Field(default_factory=dict)


def build_workflow_router(db):
    # Mounted inside the existing /v1 M5 router so these paths stay /api/v1/...
    router = APIRouter(tags=["workflow"])

    async def _user(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        return await resolve_identity(db, sid)

    async def _project(project_id: str, user: CurrentUser):
        if not (user.is_authenticated or user.is_demo) or not user.creator_id:
            raise AppError(Codes.UNAUTHENTICATED, "Sign in to continue", status_code=401)
        item = await ProjectRepo(db).get_owned(project_id, user.creator_id)
        if not item:
            raise AppError(Codes.NOT_FOUND, "Project not found", status_code=404)
        return item

    @router.get("/projects/{project_id}/foundation")
    async def get_foundation(project_id: str, user: CurrentUser = Depends(_user)):
        project = await _project(project_id, user)
        item = await ProjectFoundationRepo(db).get(project.id, project.creator_id)
        if not item:
            return {"foundation": None}
        return {"foundation": item.model_dump()}

    @router.post("/projects/{project_id}/foundation/understand")
    async def understand_foundation(project_id: str, body: FoundationInput, user: CurrentUser = Depends(_user)):
        project = await _project(project_id, user)
        foundation, reasoning = await build_project_foundation(project, body.message)
        foundation = await ProjectFoundationRepo(db).upsert(foundation)
        await LearningSignalRepo(db).add(LearningSignal(
            creator_id=project.creator_id, project_id=project.id,
            signal_type="project_intent_expressed", target_type="project_foundation",
            target_id=foundation.id, strength="very_strong", payload={"message": body.message},
        ))
        await ActivityEventRepo(db).add(project.id, project.creator_id, "project_foundation_updated", {
            "version": foundation.version, "starting_mode": reasoning.starting_mode,
            "can_ideate_now": reasoning.can_ideate_now,
        })
        return {
            "foundation": foundation.model_dump(),
            "starting_mode": reasoning.starting_mode,
            "can_ideate_now": reasoning.can_ideate_now,
            "next_question": reasoning.next_question,
        }

    @router.patch("/projects/{project_id}/foundation")
    async def patch_foundation(project_id: str, body: FoundationPatch, user: CurrentUser = Depends(_user)):
        project = await _project(project_id, user)
        patch = body.model_dump(exclude_none=True)
        field_names = {"vision", "context", "goal", "audience", "creator_perspective", "platform_format"}
        current = await ProjectFoundationRepo(db).get(project.id, project.creator_id)
        if not current:
            raise AppError(Codes.NOT_FOUND, "Project foundation not created yet", status_code=404)
        normalized = {}
        for key, value in patch.items():
            normalized[key] = FoundationField(value=value, origin="confirmed", confidence=1.0).model_dump() if key in field_names else value
        item = await ProjectFoundationRepo(db).patch(project.id, project.creator_id, normalized)
        await LearningSignalRepo(db).add(LearningSignal(
            creator_id=project.creator_id, project_id=project.id,
            signal_type="project_foundation_corrected", target_type="project_foundation",
            target_id=item.id, strength="very_strong", payload={"fields": sorted(patch.keys())},
        ))
        return {"foundation": item.model_dump()}

    @router.post("/projects/{project_id}/learning-signals")
    async def capture_signal(project_id: str, body: SignalInput, user: CurrentUser = Depends(_user)):
        project = await _project(project_id, user)
        if body.strength not in {"weak", "medium", "strong", "very_strong"}:
            raise AppError(Codes.INVALID_INPUT, "Invalid signal strength", status_code=400)
        signal = LearningSignal(
            creator_id=project.creator_id, project_id=project.id,
            signal_type=body.signal_type, target_type=body.target_type,
            target_id=body.target_id, strength=body.strength, payload=body.payload,
        )
        await LearningSignalRepo(db).add(signal)
        return signal.model_dump()

    @router.get("/creator/learning-context")
    async def learning_context(user: CurrentUser = Depends(_user)):
        if not (user.is_authenticated or user.is_demo) or not user.creator_id:
            raise AppError(Codes.UNAUTHENTICATED, "Sign in to continue", status_code=401)
        prefs = await PreferenceEvidenceRepo(db).list_active(user.creator_id)
        return {"preferences": [p.model_dump() for p in prefs]}

    return router
