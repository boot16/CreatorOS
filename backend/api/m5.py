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
from models.domain import IdeaUnderstanding, CreativeObject
from repositories import ProjectRepo, ActivityEventRepo, CreativeObjectRepo
from repositories.idea_understanding import IdeaUnderstandingRepo
from repositories.creative_directions import CreativeDirectionRepo, DirectionReadinessRepo
from repositories.creative_plans import CreativePlanRepo
from services.idea_understanding import understand_idea
from services.creative_directions import generate_creative_directions
from services.direction_development import refine_direction, combine_directions, assess_direction_readiness
from services.planning import requirements_for, generate_reel_plan


_SCALAR_FIELDS = {
    "subject", "creator_perspective", "core_claim", "intent",
    "target_audience", "desired_effect",
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


class DirectionRefineRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=3000)


class DirectionCombineRequest(BaseModel):
    secondary_direction_id: str = Field(min_length=1, max_length=200)
    instruction: str = Field(default="", max_length=3000)


def _response(item: IdeaUnderstanding) -> IdeaUnderstandingResponse:
    return IdeaUnderstandingResponse(**item.model_dump())


def _direction_markdown(item) -> str:
    lines = [
        f"## Direction\n{item.title}",
        f"## Premise\n{item.premise}",
        f"## Angle\n{item.angle}",
        f"## Audience promise\n{item.audience_promise}",
        f"## Creative treatment\n{item.creative_treatment}",
        f"## Narrative shape\n{item.narrative_shape}",
        f"## Format fit\n{item.format_fit}",
        f"## Why this direction\n{item.why_this_direction}",
    ]
    if item.emotional_movement:
        lines.append(f"## Emotional movement\n{item.emotional_movement}")
    if item.risks:
        lines.append("## Risks / things to solve\n" + "\n".join(f"- {x}" for x in item.risks))
    if item.unresolved_questions:
        lines.append("## Unresolved questions\n" + "\n".join(f"- {x}" for x in item.unresolved_questions))
    return "\n\n".join(lines).strip()


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

    async def _sync_direction_artifact(project, item):
        repo = CreativeObjectRepo(db)
        objects = await repo.list_for_project(project.id)
        existing = next(
            (obj for obj in objects if (obj.type.value if hasattr(obj.type, "value") else obj.type) == "direction"),
            None,
        )
        content = _direction_markdown(item)
        if existing:
            await repo.update(existing.id, project.id, {"title": item.title[:120], "content": content})
        else:
            await repo.create(CreativeObject(
                project_id=project.id,
                type="direction",
                title=item.title[:120],
                content=content,
            ))

    @router.get("/projects/{project_id}/idea-understanding", response_model=IdeaUnderstandingResponse)
    async def get_idea_understanding(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        item = await IdeaUnderstandingRepo(db).get(project.id, project.creator_id)
        if not item:
            raise AppError(Codes.NOT_FOUND, "Idea understanding not created yet", status_code=404)
        return _response(item)

    @router.post("/projects/{project_id}/idea-understanding/generate", response_model=IdeaUnderstandingResponse)
    async def generate_idea_understanding(project_id: str, body: IdeaUnderstandRequest, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        get_rate_limiter().check(f"idea-understanding-{project.creator_id}", *BUDGETS["project_ai_generate"])
        item = await understand_idea(project, body.raw_idea)
        item = await IdeaUnderstandingRepo(db).upsert(item)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "idea_understanding_generated", {
            "version": item.version,
            "material_unknown_count": len(item.material_unknowns),
        })
        return _response(item)

    @router.patch("/projects/{project_id}/idea-understanding", response_model=IdeaUnderstandingResponse)
    async def confirm_idea_understanding(project_id: str, body: IdeaUnderstandingPatch, user: CurrentUser = Depends(_user_dep)):
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
        await ActivityEventRepo(db).add(project.id, project.creator_id, "idea_understanding_confirmed", {
            "version": item.version,
            "fields": sorted(patch.keys()),
        })
        return _response(item)

    @router.get("/projects/{project_id}/creative-directions")
    async def list_creative_directions(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        items = await CreativeDirectionRepo(db).list_for_project(project.id, project.creator_id)
        return {"directions": [item.model_dump() for item in items]}

    @router.post("/projects/{project_id}/creative-directions/generate")
    async def create_creative_directions(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        understanding = await IdeaUnderstandingRepo(db).get(project.id, project.creator_id)
        if not understanding:
            raise AppError(Codes.INVALID_INPUT, "Understand the idea before generating creative directions", status_code=409)
        get_rate_limiter().check(f"creative-directions-v2-{project.creator_id}", *BUDGETS["project_ai_generate"])
        items = await generate_creative_directions(project, understanding)
        await CreativeDirectionRepo(db).insert_many(items)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "creative_directions_generated", {
            "batch_id": items[0].batch_id if items else None,
            "count": len(items),
            "understanding_version": understanding.version,
        })
        return {"directions": [item.model_dump() for item in items]}

    @router.put("/projects/{project_id}/creative-directions/{direction_id}/select")
    async def select_creative_direction(project_id: str, direction_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        item = await CreativeDirectionRepo(db).mark_selected(direction_id, project.id, project.creator_id)
        if not item:
            raise AppError(Codes.NOT_FOUND, "Creative direction not found", status_code=404)
        await _sync_direction_artifact(project, item)
        current_status = project.status.value if hasattr(project.status, "value") else project.status
        if current_status in {"idea", "researching"}:
            await ProjectRepo(db).update(project.id, project.creator_id, {"status": "developing"})
        await ActivityEventRepo(db).add(project.id, project.creator_id, "creative_direction_selected", {
            "direction_id": item.id, "title": item.title[:160], "revision": item.revision,
        })
        return item.model_dump()

    @router.put("/projects/{project_id}/creative-directions/{direction_id}/reject")
    async def reject_creative_direction(project_id: str, direction_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        item = await CreativeDirectionRepo(db).mark_rejected(direction_id, project.id, project.creator_id)
        if not item:
            raise AppError(Codes.NOT_FOUND, "Creative direction not found", status_code=404)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "creative_direction_rejected", {
            "direction_id": item.id, "title": item.title[:160],
        })
        return item.model_dump()

    @router.post("/projects/{project_id}/creative-directions/{direction_id}/refine")
    async def refine_creative_direction(project_id: str, direction_id: str, body: DirectionRefineRequest, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        source = await CreativeDirectionRepo(db).get(direction_id, project.id, project.creator_id)
        if not source:
            raise AppError(Codes.NOT_FOUND, "Creative direction not found", status_code=404)
        get_rate_limiter().check(f"creative-direction-refine-{project.creator_id}", *BUDGETS["project_ai_generate"])
        item = await refine_direction(project, source, body.instruction)
        await CreativeDirectionRepo(db).insert(item)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "creative_direction_refined", {
            "source_direction_id": source.id,
            "direction_id": item.id,
            "revision": item.revision,
        })
        return item.model_dump()

    @router.post("/projects/{project_id}/creative-directions/{direction_id}/combine")
    async def combine_creative_direction(project_id: str, direction_id: str, body: DirectionCombineRequest, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        primary = await CreativeDirectionRepo(db).get(direction_id, project.id, project.creator_id)
        secondary = await CreativeDirectionRepo(db).get(body.secondary_direction_id, project.id, project.creator_id)
        if not primary or not secondary:
            raise AppError(Codes.NOT_FOUND, "Creative direction not found", status_code=404)
        if primary.id == secondary.id:
            raise AppError(Codes.INVALID_INPUT, "Choose two different directions to combine", status_code=400)
        get_rate_limiter().check(f"creative-direction-combine-{project.creator_id}", *BUDGETS["project_ai_generate"])
        item = await combine_directions(project, primary, secondary, body.instruction)
        await CreativeDirectionRepo(db).insert(item)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "creative_directions_combined", {
            "parent_direction_ids": item.parent_direction_ids,
            "direction_id": item.id,
            "revision": item.revision,
        })
        return item.model_dump()

    @router.get("/projects/{project_id}/direction-readiness")
    async def get_direction_readiness(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        selected = await CreativeDirectionRepo(db).get_selected(project.id, project.creator_id)
        if not selected:
            raise AppError(Codes.INVALID_INPUT, "Select a creative direction first", status_code=409)
        item = await DirectionReadinessRepo(db).get_current(project.id, project.creator_id, selected.id, selected.revision)
        if not item:
            raise AppError(Codes.NOT_FOUND, "Readiness has not been assessed yet", status_code=404)
        return item.model_dump()

    @router.post("/projects/{project_id}/direction-readiness/assess")
    async def assess_selected_direction(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        selected = await CreativeDirectionRepo(db).get_selected(project.id, project.creator_id)
        if not selected:
            raise AppError(Codes.INVALID_INPUT, "Select a creative direction first", status_code=409)
        get_rate_limiter().check(f"direction-readiness-{project.creator_id}", *BUDGETS["project_ai_generate"])
        item = await assess_direction_readiness(project, selected)
        await DirectionReadinessRepo(db).upsert(item)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "direction_readiness_assessed", {
            "direction_id": selected.id,
            "revision": selected.revision,
            "status": item.overall_status,
            "research_need_count": len(item.research_needs),
        })
        return item.model_dump()

    # ----- M5.1 deterministic requirements + medium-aware plan -----
    @router.get("/projects/{project_id}/planning-requirements")
    async def get_planning_requirements(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        content_type = project.content_type.value if hasattr(project.content_type, "value") else project.content_type
        requirements = requirements_for(content_type)
        if not requirements:
            return {
                "content_type": content_type,
                "supported": False,
                "requirements": [],
                "message": "Deep planning is not implemented for this format yet.",
            }
        return {
            "content_type": content_type,
            "supported": True,
            "requirements": [r.model_dump() for r in requirements],
        }

    @router.get("/projects/{project_id}/creative-plan")
    async def get_creative_plan(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        selected = await CreativeDirectionRepo(db).get_selected(project.id, project.creator_id)
        if not selected:
            raise AppError(Codes.INVALID_INPUT, "Select a creative direction first", status_code=409)
        item = await CreativePlanRepo(db).latest_for_direction(project.id, project.creator_id, selected.id, selected.revision)
        if not item:
            raise AppError(Codes.NOT_FOUND, "Creative plan has not been generated yet", status_code=404)
        return item.model_dump()

    @router.post("/projects/{project_id}/creative-plan/generate")
    async def generate_creative_plan(project_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        content_type = project.content_type.value if hasattr(project.content_type, "value") else project.content_type
        if content_type != "instagram_reel":
            raise AppError(Codes.INVALID_INPUT, "Deep creative planning currently supports Instagram Reels first", status_code=409)
        selected = await CreativeDirectionRepo(db).get_selected(project.id, project.creator_id)
        if not selected:
            raise AppError(Codes.INVALID_INPUT, "Select a creative direction first", status_code=409)
        readiness = await DirectionReadinessRepo(db).get_current(project.id, project.creator_id, selected.id, selected.revision)
        get_rate_limiter().check(f"creative-plan-{project.creator_id}", *BUDGETS["project_ai_generate"])
        item = await generate_reel_plan(project, selected, readiness)
        await CreativePlanRepo(db).create_next(item)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "creative_plan_generated", {
            "plan_id": item.id,
            "version": item.version,
            "direction_id": selected.id,
            "direction_revision": selected.revision,
            "research_requirement_count": len(item.research_requirements),
        })
        return item.model_dump()

    @router.put("/projects/{project_id}/creative-plan/{plan_id}/approve")
    async def approve_creative_plan(project_id: str, plan_id: str, user: CurrentUser = Depends(_user_dep)):
        project = await _owned_project(project_id, user)
        item = await CreativePlanRepo(db).update_status(plan_id, project.id, project.creator_id, "approved")
        if not item:
            raise AppError(Codes.NOT_FOUND, "Creative plan not found", status_code=404)
        await ActivityEventRepo(db).add(project.id, project.creator_id, "creative_plan_approved", {
            "plan_id": item.id, "version": item.version,
        })
        return item.model_dump()

    return router
