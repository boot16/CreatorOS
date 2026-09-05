"""Production v1 API — authenticated identity + workspace-scoped operations."""
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Body

from core.config import get_settings
from core.errors import AppError, Codes
from core.identity import CurrentUser, SESSION_COOKIE, resolve_identity, require_real_auth, require_creator
from core.rate_limit import get_rate_limiter, BUDGETS
from api.schemas import (
    CurrentCreatorContext, CreatorIntentBody, CreatorIntentResponse,
    SyncResultResponse, CreatorDNAStatusResponse, ConnectedPlatformResponse,
    ProjectCreateBody, ProjectUpdateBody, ProjectResponse, ProjectBriefBody,
    CreativeObjectBody, CreativeObjectUpdateBody, CreativeObjectResponse,
    ActivityEventResponse,
    ResearchRequest, SourceBody, SourceResponse, DirectionSelectBody,
    EditRequest, ChatRequest, ChatMessageResponse,
    OnboardingBody, CreatorContextResponse,
    _CONTENT_TYPES, _STATUSES, _CREATIVE_TYPES,
)
from repositories import IntentRepo, DNARepo, PlatformRepo, CreatorRepo, ProjectRepo, CreativeObjectRepo, ActivityEventRepo, ProjectSourceRepo, ProjectChatRepo
from models.domain import Project, CreativeObject, ProjectBrief, ProjectSource, ProjectChatMessage
from services.youtube_sync import YouTubeSyncService
from services.project_ai import (
    ProjectContext, run_research, run_directions, run_outline, run_content,
    run_edit, run_critique, run_assistant_reply,
)
from services.creator_context import load_creator_context
from services.dna_generator import generate_initial_dna
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
        onboarding_complete = False
        if user.creator_id and user.is_authenticated:
            dna = await DNARepo(db).latest(user.creator_id)
            yt_platform = await PlatformRepo(db).get_for_creator(user.creator_id, "youtube")
            yt_connected = yt_platform is not None
            onboarding_complete = dna is not None and dna.status.value == "ready"
        elif user.is_demo:
            # Demo user is always "onboarded" — seeded Alex DNA
            onboarding_complete = True
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
            dna_status=dna_status,
            onboarding_complete=onboarding_complete,
        )

    @router.get("/creator-context", response_model=CreatorContextResponse)
    async def creator_context(user: CurrentUser = Depends(_user_dep)):
        """Central creator context — creator profile + DNA + intent + platforms.
        AI features consume this so every surface speaks about the same creator."""
        ctx = await load_creator_context(db, user)
        return CreatorContextResponse(**ctx.to_dict())

    @router.post("/onboarding", response_model=CreatorContextResponse)
    async def onboarding(body: OnboardingBody, user: CurrentUser = Depends(_user_dep)):
        """First-run creator onboarding. Requires REAL auth (demo user is auto-onboarded).
        Generates initial CreatorDNA and returns the fresh creator context."""
        require_real_auth(user)
        creator_id = require_creator(user)
        get_rate_limiter().check(f"onboarding-{user.user_id}", 10, 3600)
        # Also persist a lightweight CreatorIntent
        intent_patch = {
            "primary_goal": (body.goals[0] if body.goals else None),
            "secondary_goals": body.goals[1:] if len(body.goals) > 1 else [],
            "desired_topics": body.topics,
            "formats_to_explore": body.preferred_formats,
            "target_audience": body.intended_audience,
        }
        await IntentRepo(db).upsert(creator_id, {k: v for k, v in intent_patch.items() if v})
        await generate_initial_dna(
            db, creator_id,
            creator_types=body.creator_types,
            onboarding_text=body.onboarding_text,
            topics=body.topics,
            intended_audience=body.intended_audience,
            platforms=body.platforms,
            preferred_formats=body.preferred_formats,
            goals=body.goals,
            connected_sources=body.connected_sources,
        )
        ctx = await load_creator_context(db, user)
        return CreatorContextResponse(**ctx.to_dict())

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

    @router.get("/dna", response_model=CreatorDNAStatusResponse)
    async def dna_status(user: CurrentUser = Depends(_user_dep)):
        require_real_auth(user)
        creator_id = require_creator(user)
        dna = await DNARepo(db).latest(creator_id)
        if not dna:
            return CreatorDNAStatusResponse(creator_id=creator_id, status="not_computed")
        return CreatorDNAStatusResponse(
            creator_id=creator_id,
            status=dna.status.value,
            version=dna.version,
            computed_at=dna.computed_at,
        )

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

    # ---------------- M2: Projects ----------------
    def _project_platform_for(content_type: str) -> str:
        if content_type == "youtube_video":
            return "youtube"
        return "instagram"

    def _project_to_response(p: Project) -> ProjectResponse:
        return ProjectResponse(
            id=p.id, creator_id=p.creator_id, workspace_id=p.workspace_id,
            title=p.title,
            content_type=p.content_type.value if hasattr(p.content_type, "value") else p.content_type,
            platform=p.platform.value if hasattr(p.platform, "value") else p.platform,
            objective=p.objective,
            status=p.status.value if hasattr(p.status, "value") else p.status,
            brief=ProjectBriefBody(**p.brief.model_dump()),
            created_at=p.created_at, updated_at=p.updated_at,
        )

    def _obj_to_response(o: CreativeObject) -> CreativeObjectResponse:
        return CreativeObjectResponse(
            id=o.id, project_id=o.project_id,
            type=o.type.value if hasattr(o.type, "value") else o.type,
            title=o.title, content=o.content,
            created_at=o.created_at, updated_at=o.updated_at,
        )

    async def _require_owned_project(project_id: str, user: CurrentUser) -> Project:
        """Load project + enforce ownership. Never leak existence to non-owners."""
        require_creator(user)
        p = await ProjectRepo(db).get_owned(project_id, user.creator_id)
        if not p:
            raise AppError(Codes.NOT_FOUND, "Project not found", status_code=404)
        return p

    def _require_authed(user: CurrentUser) -> tuple[str, str]:
        """M2 works for any resolved identity (real user OR demo). Requires creator + workspace."""
        if not (user.is_authenticated or user.is_demo):
            raise AppError(Codes.UNAUTHENTICATED, "Sign in to continue", status_code=401)
        if not user.creator_id or not user.workspace_id:
            raise AppError(Codes.NOT_FOUND, "No creator/workspace for this account", status_code=404)
        return user.creator_id, user.workspace_id

    @router.post("/projects", response_model=ProjectResponse)
    async def create_project(body: ProjectCreateBody, user: CurrentUser = Depends(_user_dep)):
        creator_id, workspace_id = _require_authed(user)
        if body.content_type not in _CONTENT_TYPES:
            raise AppError(Codes.INVALID_INPUT, f"Unsupported content_type", status_code=400)
        platform = _project_platform_for(body.content_type)
        proj = Project(
            creator_id=creator_id, workspace_id=workspace_id,
            title=body.title.strip(), content_type=body.content_type, platform=platform,
            objective=body.objective,
        )
        # Pre-fill working_title in brief for convenience
        proj.brief.working_title = proj.title
        proj.brief.objective = proj.objective
        await ProjectRepo(db).create(proj)
        await ActivityEventRepo(db).add(
            proj.id, creator_id, "project_created",
            {"title": proj.title, "content_type": proj.content_type.value if hasattr(proj.content_type, "value") else proj.content_type},
        )
        return _project_to_response(proj)

    @router.get("/projects", response_model=list[ProjectResponse])
    async def list_projects(user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        items = await ProjectRepo(db).list_for_creator(creator_id)
        return [_project_to_response(p) for p in items]

    @router.get("/projects/{project_id}", response_model=ProjectResponse)
    async def get_project(project_id: str, user: CurrentUser = Depends(_user_dep)):
        _require_authed(user)
        p = await _require_owned_project(project_id, user)
        return _project_to_response(p)

    @router.patch("/projects/{project_id}", response_model=ProjectResponse)
    async def update_project(project_id: str, body: ProjectUpdateBody, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        existing = await _require_owned_project(project_id, user)
        patch = body.model_dump(exclude_none=True)
        if "status" in patch and patch["status"] not in _STATUSES:
            raise AppError(Codes.INVALID_INPUT, "Invalid status", status_code=400)
        if "title" in patch:
            patch["title"] = patch["title"].strip()
            if not patch["title"]:
                raise AppError(Codes.INVALID_INPUT, "Title cannot be empty", status_code=400)
        updated = await ProjectRepo(db).update(project_id, creator_id, patch)
        if not updated:
            raise AppError(Codes.NOT_FOUND, "Project not found", status_code=404)
        # Activity
        if "status" in patch and patch["status"] != (existing.status.value if hasattr(existing.status, "value") else existing.status):
            event = "project_discarded" if patch["status"] == "discarded" else "project_status_changed"
            await ActivityEventRepo(db).add(project_id, creator_id, event, {"status": patch["status"]})
        else:
            await ActivityEventRepo(db).add(project_id, creator_id, "project_updated", {"fields": list(patch.keys())})
        return _project_to_response(updated)

    @router.put("/projects/{project_id}/brief", response_model=ProjectResponse)
    async def update_brief(project_id: str, body: ProjectBriefBody, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        await _require_owned_project(project_id, user)
        # Merge: any non-None field overwrites; None keeps existing value.
        patch = body.model_dump()
        current = await ProjectRepo(db).get_owned(project_id, creator_id)
        merged = current.brief.model_dump()
        for k, v in patch.items():
            if v is not None:
                merged[k] = v
        updated = await ProjectRepo(db).update(project_id, creator_id, {"brief": merged})
        await ActivityEventRepo(db).add(project_id, creator_id, "brief_updated", {"fields": [k for k, v in patch.items() if v is not None]})
        return _project_to_response(updated)

    @router.get("/projects/{project_id}/creative-objects", response_model=list[CreativeObjectResponse])
    async def list_creative_objects(project_id: str, user: CurrentUser = Depends(_user_dep)):
        _require_authed(user)
        await _require_owned_project(project_id, user)
        items = await CreativeObjectRepo(db).list_for_project(project_id)
        return [_obj_to_response(o) for o in items]

    @router.post("/projects/{project_id}/creative-objects", response_model=CreativeObjectResponse)
    async def create_creative_object(project_id: str, body: CreativeObjectBody, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        await _require_owned_project(project_id, user)
        if body.type not in _CREATIVE_TYPES:
            raise AppError(Codes.INVALID_INPUT, "Unsupported creative object type", status_code=400)
        obj = CreativeObject(project_id=project_id, type=body.type, title=body.title, content=body.content or "")
        await CreativeObjectRepo(db).create(obj)
        await ActivityEventRepo(db).add(project_id, creator_id, "creative_object_created", {"type": obj.type.value if hasattr(obj.type, "value") else obj.type, "id": obj.id})
        return _obj_to_response(obj)

    @router.patch("/projects/{project_id}/creative-objects/{obj_id}", response_model=CreativeObjectResponse)
    async def update_creative_object(project_id: str, obj_id: str, body: CreativeObjectUpdateBody, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        await _require_owned_project(project_id, user)
        patch = body.model_dump(exclude_none=True)
        updated = await CreativeObjectRepo(db).update(obj_id, project_id, patch)
        if not updated:
            raise AppError(Codes.NOT_FOUND, "Creative object not found", status_code=404)
        await ActivityEventRepo(db).add(project_id, creator_id, "creative_object_updated", {"id": obj_id, "fields": list(patch.keys())})
        return _obj_to_response(updated)

    @router.delete("/projects/{project_id}/creative-objects/{obj_id}")
    async def delete_creative_object(project_id: str, obj_id: str, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        await _require_owned_project(project_id, user)
        ok = await CreativeObjectRepo(db).delete(obj_id, project_id)
        if not ok:
            raise AppError(Codes.NOT_FOUND, "Creative object not found", status_code=404)
        await ActivityEventRepo(db).add(project_id, creator_id, "creative_object_deleted", {"id": obj_id})
        return {"ok": True}

    @router.get("/projects/{project_id}/activity", response_model=list[ActivityEventResponse])
    async def project_activity(project_id: str, user: CurrentUser = Depends(_user_dep)):
        _require_authed(user)
        await _require_owned_project(project_id, user)
        items = await ActivityEventRepo(db).list_for_project(project_id)
        return [ActivityEventResponse(**e.model_dump()) for e in items]

    # ---------------- M3: Project-Aware AI ----------------
    def _co_to_response(o: CreativeObject) -> CreativeObjectResponse:
        return _obj_to_response(o)

    async def _upsert_singleton_creative_object(project_id: str, obj_type: str, title: str, content: str) -> CreativeObject:
        """Some project artifacts (research, direction, outline) are singletons — only one active per project.
        We upsert by finding an existing object of that type and updating it; otherwise create fresh."""
        objs = await CreativeObjectRepo(db).list_for_project(project_id)
        existing = next((o for o in objs if (o.type.value if hasattr(o.type, "value") else o.type) == obj_type), None)
        if existing:
            updated = await CreativeObjectRepo(db).update(existing.id, project_id, {"title": title, "content": content})
            return updated
        new_obj = CreativeObject(project_id=project_id, type=obj_type, title=title, content=content)
        await CreativeObjectRepo(db).create(new_obj)
        return new_obj

    def _format_research_markdown(r) -> str:
        """Deterministic markdown rendering of ResearchOutput so it lives inside a CreativeObject as editable text."""
        lines = []
        if getattr(r, "summary", ""):
            lines += ["## Summary", r.summary]
        def _bullets(title, items):
            items = [i for i in (items or []) if i]
            if not items: return
            lines.append(f"\n## {title}")
            lines.extend(f"- {i}" for i in items)
        _bullets("Key facts", r.key_facts)
        _bullets("Insights", r.insights)
        _bullets("Perspectives", r.perspectives)
        _bullets("Content opportunities", r.opportunities)
        _bullets("Open questions", r.open_questions)
        return "\n".join(lines).strip()

    def _format_direction_markdown(d) -> str:
        return (
            f"## Angle\n{d.get('angle','')}\n\n"
            f"## Audience takeaway\n{d.get('audience_takeaway','')}\n\n"
            f"## Format / approach\n{d.get('format','')}\n\n"
            f"## Tone\n{d.get('tone','')}\n\n"
            f"## Why this works\n{d.get('why_it_works','')}"
        ).strip()

    def _format_outline_markdown(o) -> str:
        lines = []
        for section in o.outline:
            lines.append(f"## {section.label}")
            for b in section.beats:
                lines.append(f"- {b}")
            lines.append("")
        return "\n".join(lines).strip()

    async def _load_context(project: Project, user: CurrentUser) -> ProjectContext:
        return await ProjectContext.load(db, project, user)

    def _bump_status_if(project: Project, current_allowed: set, new_status: str):
        """Only advance status forward from allowed early stages — never regress a creator who is already ahead."""
        cur = project.status.value if hasattr(project.status, "value") else project.status
        return new_status if cur in current_allowed else None

    # ----- Sources CRUD -----
    @router.post("/projects/{project_id}/sources", response_model=SourceResponse)
    async def add_source(project_id: str, body: SourceBody, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        await _require_owned_project(project_id, user)
        if body.source_type not in {"url", "text"}:
            raise AppError(Codes.INVALID_INPUT, "source_type must be 'url' or 'text'", status_code=400)
        if body.source_type == "url" and not (body.url and body.url.strip()):
            raise AppError(Codes.INVALID_INPUT, "URL required for url source", status_code=400)
        src = ProjectSource(
            project_id=project_id, title=body.title.strip(),
            url=(body.url.strip() if body.url else None),
            source_type=body.source_type, content=body.content or "",
        )
        await ProjectSourceRepo(db).create(src)
        await ActivityEventRepo(db).add(project_id, creator_id, "source_added", {"id": src.id, "type": src.source_type})
        return SourceResponse(**src.model_dump())

    @router.get("/projects/{project_id}/sources", response_model=list[SourceResponse])
    async def list_sources(project_id: str, user: CurrentUser = Depends(_user_dep)):
        _require_authed(user)
        await _require_owned_project(project_id, user)
        items = await ProjectSourceRepo(db).list_for_project(project_id)
        return [SourceResponse(**s.model_dump()) for s in items]

    @router.delete("/projects/{project_id}/sources/{source_id}")
    async def delete_source(project_id: str, source_id: str, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        await _require_owned_project(project_id, user)
        ok = await ProjectSourceRepo(db).delete(source_id, project_id)
        if not ok:
            raise AppError(Codes.NOT_FOUND, "Source not found", status_code=404)
        await ActivityEventRepo(db).add(project_id, creator_id, "source_deleted", {"id": source_id})
        return {"ok": True}

    # ----- AI: Research -----
    @router.post("/projects/{project_id}/ai/research")
    async def ai_research(project_id: str, body: ResearchRequest, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        proj = await _require_owned_project(project_id, user)
        get_rate_limiter().check(f"proj-ai-{creator_id}", *BUDGETS["project_ai_generate"])
        ctx = await _load_context(proj, user)
        try:
            result = await run_research(ctx, body.question)
        except AppError:
            raise
        markdown = _format_research_markdown(result)
        obj = await _upsert_singleton_creative_object(project_id, "research", "Research brief", markdown)
        # Status auto-advance idea → researching
        bump = _bump_status_if(proj, {"idea"}, "researching")
        if bump:
            await ProjectRepo(db).update(project_id, creator_id, {"status": bump})
            await ActivityEventRepo(db).add(project_id, creator_id, "project_status_changed", {"status": bump})
        await ActivityEventRepo(db).add(project_id, creator_id, "research_generated", {"question": body.question[:200]})
        return {
            "creative_object": _obj_to_response(obj),
            "structured": result.model_dump(),
        }

    # ----- AI: Directions -----
    @router.post("/projects/{project_id}/ai/directions")
    async def ai_directions(project_id: str, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        proj = await _require_owned_project(project_id, user)
        get_rate_limiter().check(f"proj-ai-{creator_id}", *BUDGETS["project_ai_generate"])
        ctx = await _load_context(proj, user)
        result = await run_directions(ctx)
        return {"directions": [d.model_dump() for d in result.directions]}

    @router.put("/projects/{project_id}/ai/direction/selected", response_model=CreativeObjectResponse)
    async def ai_direction_select(project_id: str, body: DirectionSelectBody, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        proj = await _require_owned_project(project_id, user)
        markdown = _format_direction_markdown(body.model_dump())
        title = body.angle[:120] if body.angle else "Selected direction"
        obj = await _upsert_singleton_creative_object(project_id, "direction", title, markdown)
        bump = _bump_status_if(proj, {"idea", "researching"}, "developing")
        if bump:
            await ProjectRepo(db).update(project_id, creator_id, {"status": bump})
            await ActivityEventRepo(db).add(project_id, creator_id, "project_status_changed", {"status": bump})
        await ActivityEventRepo(db).add(project_id, creator_id, "direction_selected", {"angle": body.angle[:200]})
        return _obj_to_response(obj)

    # ----- AI: Outline -----
    @router.post("/projects/{project_id}/ai/outline")
    async def ai_outline(project_id: str, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        proj = await _require_owned_project(project_id, user)
        get_rate_limiter().check(f"proj-ai-{creator_id}", *BUDGETS["project_ai_generate"])
        ctx = await _load_context(proj, user)
        result = await run_outline(ctx)
        markdown = _format_outline_markdown(result)
        obj = await _upsert_singleton_creative_object(project_id, "outline", "Outline", markdown)
        bump = _bump_status_if(proj, {"idea", "researching", "developing"}, "writing")
        if bump:
            await ProjectRepo(db).update(project_id, creator_id, {"status": bump})
            await ActivityEventRepo(db).add(project_id, creator_id, "project_status_changed", {"status": bump})
        await ActivityEventRepo(db).add(project_id, creator_id, "outline_generated", {})
        return {
            "creative_object": _obj_to_response(obj),
            "structured": result.model_dump(),
        }

    # ----- AI: Content -----
    @router.post("/projects/{project_id}/ai/content", response_model=CreativeObjectResponse)
    async def ai_content(project_id: str, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        proj = await _require_owned_project(project_id, user)
        get_rate_limiter().check(f"proj-ai-{creator_id}", *BUDGETS["project_ai_generate"])
        ctx = await _load_context(proj, user)
        text, out_type = await run_content(ctx)
        # Always create a NEW creative object — never overwrite existing script/caption/carousel silently
        new_obj = CreativeObject(
            project_id=project_id, type=out_type,
            title=f"AI draft — {proj.title[:80]}", content=text,
        )
        await CreativeObjectRepo(db).create(new_obj)
        bump = _bump_status_if(proj, {"idea", "researching", "developing"}, "writing")
        if bump:
            await ProjectRepo(db).update(project_id, creator_id, {"status": bump})
            await ActivityEventRepo(db).add(project_id, creator_id, "project_status_changed", {"status": bump})
        await ActivityEventRepo(db).add(project_id, creator_id, "content_generated", {"type": out_type, "id": new_obj.id})
        return _obj_to_response(new_obj)

    # ----- AI: Edit / critique — return proposals; NEVER overwrite unless caller commits via PATCH -----
    @router.post("/projects/{project_id}/ai/edit")
    async def ai_edit(project_id: str, body: EditRequest, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        proj = await _require_owned_project(project_id, user)
        get_rate_limiter().check(f"proj-ai-{creator_id}", *BUDGETS["project_ai_generate"])
        ctx = await _load_context(proj, user)
        if body.action == "critique":
            result = await run_critique(ctx, body.content)
            return {"action": "critique", "critique": result.model_dump()}
        if body.action not in {"rewrite", "improve_hook"}:
            raise AppError(Codes.INVALID_INPUT, "Unknown action", status_code=400)
        proposal = await run_edit(ctx, action=body.action, content=body.content, instruction=body.instruction or "")
        return {"action": body.action, "proposal": proposal}

    # ----- AI: Project-scoped assistant chat -----
    @router.get("/projects/{project_id}/ai/chat", response_model=list[ChatMessageResponse])
    async def ai_chat_history(project_id: str, user: CurrentUser = Depends(_user_dep)):
        _require_authed(user)
        await _require_owned_project(project_id, user)
        items = await ProjectChatRepo(db).list_for_project(project_id)
        return [ChatMessageResponse(**m.model_dump()) for m in items]

    @router.post("/projects/{project_id}/ai/chat", response_model=ChatMessageResponse)
    async def ai_chat_send(project_id: str, body: ChatRequest, user: CurrentUser = Depends(_user_dep)):
        creator_id, _ = _require_authed(user)
        proj = await _require_owned_project(project_id, user)
        get_rate_limiter().check(f"proj-chat-{creator_id}", *BUDGETS["project_ai_chat"])
        # Persist user turn first — if AI fails, user turn remains visible; no destructive overwrite of anything.
        user_msg = ProjectChatMessage(
            project_id=project_id, creator_id=creator_id,
            role="user", content=body.message,
        )
        await ProjectChatRepo(db).add(user_msg)
        history_docs = await ProjectChatRepo(db).list_for_project(project_id)
        history = [{"role": m.role, "content": m.content} for m in history_docs]
        ctx = await _load_context(proj, user)
        try:
            reply_text = await run_assistant_reply(ctx, history[:-1], body.message)
        except AppError as e:
            # Persist a visible failure marker so the timeline is honest, and re-raise
            err = ProjectChatMessage(
                project_id=project_id, creator_id=creator_id,
                role="assistant", content=f"(assistant temporarily unavailable — {e.message})",
            )
            await ProjectChatRepo(db).add(err)
            raise
        assistant_msg = ProjectChatMessage(
            project_id=project_id, creator_id=creator_id,
            role="assistant", content=reply_text,
        )
        await ProjectChatRepo(db).add(assistant_msg)
        return ChatMessageResponse(**assistant_msg.model_dump())

    return router
