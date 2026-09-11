"""M5 Creative Workflow API.

Kept separate from the legacy v1 project router while M5 is introduced incrementally.
Routes still live under /api/v1 so the frontend has one stable API namespace.
"""
from typing import Optional

from fastapi import APIRouter, Cookie, Depends
from pydantic import BaseModel, Field

from core.errors import AppError, Codes
from core.identity import CurrentUser, SESSION_COOKIE, resolve_identity
from core.rate_limit import get_rate_limiter, BUDGETS
from models.domain import IdeaUnderstanding
from repositories import ProjectRepo, ActivityEventRepo
from repositories.idea_understanding import IdeaUnderstandingRepo
from services.idea_understanding import understand_idea


_SCALAR_FIELDS = {
    "subject",
    "creator_perspective",
    "core_claim",
    "intent",
    "target_audience",
    "desired_effect",
}


class IdeaUnderstandRequest(BaseModel):
    raw_idea: str = Field(min_length=3, max_length=10000)


class IdeaUnderstandingPatch(BaseModel):
    subject: Optional[str] = Field(default=None, max_length=2000)
    creator_perspective: Optional[str] = Field(default=None, max_length=4000)
    core_claim: Optional[str] = Field(default=None, max_length=4000)
    intent: Optional[str] = Field(default=None, max_length=2000)
    target_audience: Optional[str] = Field(default=None, max_length=2000)
    desired_effect: Optional[str] = Field(default=None, max_length=2000)
    assumptions: Optional[list[str]] = Field(default=None, max_length=8)
    open_questions: Optional[list[str]] = Field(default=None, max_length=6)
    material_unknowns: Optional[list[str]] = Field(default=None, max_length=6)


class IdeaUnderstandingResponse(BaseModel):
    id: str
    project_id: str
    creator_id: str
    raw_idea: str
    subject: dict
    creator_perspective: dict
    core_claim: dict
    intent: dict
    target_audience: dict
    desired_effect: dict
    assumptions: list[str]
    open_questions: list[str]
    material_unknowns: list[str]
    version: int
    created_at: str
    updated_at: str


def _response(item: IdeaUnderstanding) -> IdeaUnderstandingResponse:
    return IdeaUnderstandingResponse(**item.model_dump())


def build_m5_router(db):
    router = APIRouter(prefix="/v1", tags=["m5"])

    async def _user_dep(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)) -> CurrentUser:
        return await resolve_identity(db, sid)

    def _require_authed(user: CurrentUser) -> tuple[str, str]:
        if not (user.is_authenticated or user.is_demo):
            raise AppError(Codes.UNAUTHENTICATED, "Sign in to continue", status_code=401)
        if not user.creator_id or not user.workspace_id:
            raise AppError(Codes.NOT_FOUND, "No creator/workspace for this account", status_code=404)
        return user.creator_id, user.workspace_id

    async def _owned_project(project_id: str, user: CurrentUser):
        creator_id, _ = _require_authed(user)
        project = await ProjectRepo(db).get_owned(project_id, creator_id)
        if not project:
            raise AppError(Codes.NOT_FOUND, "Project not found", status_code=404)
        return project

    @router.get(
        "/projects/{project_id}/idea-understanding",
        response_model=IdeaUnderstandingResponse,
    )
    async def get_idea_understanding(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        item = await IdeaUnderstandingRepo(db).get(project.id, project.creator_id)
        if not item:
            raise AppError(Codes.NOT_FOUND, "Idea understanding not created yet", status_code=404)
        return _response(item)

    @router.post(
        "/projects/{project_id}/idea-understanding/generate",
        response_model=IdeaUnderstandingResponse,
    )
    async def generate_idea_understanding(
        project_id: str,
        body: IdeaUnderstandRequest,
        user: CurrentUser = Depends(_user_dep),
    ):
        project = await _owned_project(project_id, user)
        get_rate_limiter().check(
            f"idea-understanding-{project.creator_id}",
            *BUDGETS["project_ai_generate"],
        )
        item = await understand_idea(project, body.raw_idea)
        item = await IdeaUnderstandingRepo(db).upsert(item)
        await ActivityEventRepo(db).add(
            project.id,
            project.creator_id,
            "idea_understanding_generated",
            {
                "version": item.version,
                "material_unknown_count": len(item.material_unknowns),
            },
        )
        return _response(item)

    @router.patch(
        "/projects/{project_id}/idea-understanding",
        response_model=IdeaUnderstandingResponse,
    )
    async def confirm_idea_understanding(
        project_id: str,
        body: IdeaUnderstandingPatch,
        user: CurrentUser = Depends(_user_dep),
    ):
        project = await _owned_project(project_id, user)
        patch = body.model_dump(exclude_none=True)
        scalar_patch = {k: v for k, v in patch.items() if k in _SCALAR_FIELDS}
        item = await IdeaUnderstandingRepo(db).patch_confirmed_fields(
            project.id,
            project.creator_id,
            scalar_patch,
            assumptions=patch.get("assumptions"),
            open_questions=patch.get("open_questions"),
            material_unknowns=patch.get("material_unknowns"),
        )
        if not item:
            raise AppError(Codes.NOT_FOUND, "Idea understanding not created yet", status_code=404)
        await ActivityEventRepo(db).add(
            project.id,
            project.creator_id,
            "idea_understanding_confirmed",
            {"version": item.version, "fields": sorted(patch.keys())},
        )
        return _response(item)

    return router
