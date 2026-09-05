"""M3: Project-aware AI service.

Small, focused module — reuses services/llm.py for all LLM calls.
Nothing here talks to the database directly except through repos.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

from core.errors import AppError, Codes
from services.llm import call_structured, call_text
from repositories import (
    ProjectRepo, CreativeObjectRepo, ProjectSourceRepo, ActivityEventRepo,
)
from models.domain import Project, CreativeObject, ProjectSource


# ---------------- Context assembly ----------------

MAX_SOURCE_CHARS = 1200          # per source in prompt
MAX_CREATIVE_OBJECT_CHARS = 1500  # per object in context
MAX_TOTAL_CONTEXT_CHARS = 12000


def _truncate(s: str, n: int) -> str:
    if not s:
        return ""
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


class ProjectContext:
    """Assembles ONLY the trusted, owner-scoped context for an AI request."""

    def __init__(
        self,
        project: Project,
        research_obj: Optional[CreativeObject],
        direction_obj: Optional[CreativeObject],
        outline_obj: Optional[CreativeObject],
        other_objects: List[CreativeObject],
        sources: List[ProjectSource],
        creator_prompt: str = "",
    ):
        self.project = project
        self.research = research_obj
        self.direction = direction_obj
        self.outline = outline_obj
        self.other_objects = other_objects
        self.sources = sources
        self.creator_prompt = creator_prompt

    @classmethod
    async def load(cls, db, project: Project, user=None) -> "ProjectContext":
        """Load the full project context. Caller MUST have already verified ownership.
        When `user` is provided, the CreatorContext is included so AI features share
        the same creator identity across the app."""
        co_repo = CreativeObjectRepo(db)
        src_repo = ProjectSourceRepo(db)
        objs = await co_repo.list_for_project(project.id)
        research = next((o for o in objs if (o.type.value if hasattr(o.type, "value") else o.type) == "research"), None)
        direction = next((o for o in objs if (o.type.value if hasattr(o.type, "value") else o.type) == "direction"), None)
        outline = next((o for o in objs if (o.type.value if hasattr(o.type, "value") else o.type) == "outline"), None)
        special = {id(x) for x in (research, direction, outline) if x is not None}
        other = [o for o in objs if id(o) not in special]
        sources = await src_repo.list_for_project(project.id)
        creator_prompt = ""
        if user is not None:
            try:
                from services.creator_context import load_creator_context
                cctx = await load_creator_context(db, user)
                creator_prompt = cctx.render_for_prompt()
            except Exception:
                creator_prompt = ""
        return cls(project, research, direction, outline, other, sources, creator_prompt=creator_prompt)

    def render(self, *, include_content_objects: bool = True) -> str:
        """Render into a compact structured prompt block. Deterministic ordering."""
        parts = []
        if self.creator_prompt:
            parts.append(self.creator_prompt)
            parts.append("")
        p = self.project
        b = p.brief.model_dump() if hasattr(p.brief, "model_dump") else dict(p.brief or {})
        parts += ["## PROJECT", f"- id: {p.id}",
                 f"- title: {p.title}",
                 f"- content_type: {p.content_type.value if hasattr(p.content_type,'value') else p.content_type}",
                 f"- platform: {p.platform.value if hasattr(p.platform,'value') else p.platform}",
                 f"- status: {p.status.value if hasattr(p.status,'value') else p.status}"]
        if p.objective:
            parts.append(f"- objective: {p.objective}")

        parts.append("\n## BRIEF")
        for k, v in b.items():
            if v:
                parts.append(f"- {k}: {v}")

        if self.sources:
            parts.append("\n## SOURCES (user-provided)")
            for i, s in enumerate(self.sources, 1):
                head = f"[{i}] {s.title}"
                if s.url:
                    head += f" — {s.url}"
                parts.append(head)
                if s.content:
                    parts.append(_truncate(s.content, MAX_SOURCE_CHARS))

        if self.research and self.research.content:
            parts.append("\n## SAVED RESEARCH")
            parts.append(_truncate(self.research.content, MAX_CREATIVE_OBJECT_CHARS))

        if self.direction and self.direction.content:
            parts.append("\n## SELECTED CREATIVE DIRECTION")
            parts.append(_truncate(self.direction.content, MAX_CREATIVE_OBJECT_CHARS))

        if self.outline and self.outline.content:
            parts.append("\n## OUTLINE / STRUCTURE")
            parts.append(_truncate(self.outline.content, MAX_CREATIVE_OBJECT_CHARS))

        if include_content_objects and self.other_objects:
            parts.append("\n## OTHER CREATIVE OBJECTS")
            for o in self.other_objects[:5]:
                t = o.type.value if hasattr(o.type, "value") else o.type
                parts.append(f"- [{t}] {o.title or 'Untitled'}: {_truncate(o.content, 400)}")

        return _truncate("\n".join(parts), MAX_TOTAL_CONTEXT_CHARS)


# ---------------- Structured output schemas ----------------

class ResearchOutput(BaseModel):
    summary: str
    key_facts: List[str] = Field(default_factory=list, max_length=10)
    insights: List[str] = Field(default_factory=list, max_length=8)
    perspectives: List[str] = Field(default_factory=list, max_length=6)
    opportunities: List[str] = Field(default_factory=list, max_length=6)
    open_questions: List[str] = Field(default_factory=list, max_length=6)


class DirectionOption(BaseModel):
    angle: str
    audience_takeaway: str
    format: str
    tone: str
    why_it_works: str


class DirectionsOutput(BaseModel):
    directions: List[DirectionOption] = Field(min_length=2, max_length=4)


class OutlineSection(BaseModel):
    label: str
    beats: List[str] = Field(default_factory=list, max_length=8)


class OutlineOutput(BaseModel):
    outline: List[OutlineSection] = Field(min_length=2, max_length=10)


class CritiqueOutput(BaseModel):
    strengths: List[str] = Field(default_factory=list, max_length=6)
    weaknesses: List[str] = Field(default_factory=list, max_length=6)
    suggestions: List[str] = Field(default_factory=list, max_length=6)


# ---------------- AI task functions ----------------

_SYSTEM_RESEARCH = (
    "You are a senior content research analyst helping a specific creator on a specific project. "
    "Use ONLY the provided project context and sources. NEVER fabricate URLs, citations, or "
    "statistics you cannot ground in the given text. When uncertain, say so in open_questions. "
    "Return only valid JSON."
)

_SYSTEM_DIRECTIONS = (
    "You are a creative director for short-form/long-form video. Propose 2-3 DISTINCT creative "
    "directions for this specific project, grounded in its brief, research, and sources. "
    "Directions should be meaningfully different (angle, format, tone). Return only valid JSON."
)

_SYSTEM_OUTLINE_YOUTUBE = (
    "You are a top-tier YouTube writer. Build an editable outline (hook, sections with key beats, "
    "payoff). Match the selected direction and creator's tone. Return only valid JSON."
)

_SYSTEM_OUTLINE_REEL = (
    "You are an Instagram Reel writer. Build a short outline: hook, 3-5 beats, ending. Fast, punchy. "
    "Return only valid JSON."
)

_SYSTEM_OUTLINE_POST = (
    "You are an Instagram post writer. Build an outline for a single-post caption: hook line, body "
    "sections, CTA. Return only valid JSON."
)

_SYSTEM_OUTLINE_CAROUSEL = (
    "You are an Instagram carousel writer. Build a slide outline: opening slide, 5-8 middle slides, "
    "final slide/CTA. Each slide has a label and 1-3 beats. Return only valid JSON."
)

_SYSTEM_CONTENT_YOUTUBE = (
    "You are a top-tier YouTube script writer. Write a first-draft script following the outline and "
    "direction, in the creator's voice. Include HOOK, section headers, and [B-ROLL] / [ON CAMERA] "
    "notes. 700-1000 words. Return only the script text, no preamble."
)

_SYSTEM_CONTENT_REEL_SCRIPT = (
    "You are an Instagram Reel scriptwriter. Write a 30-45 second script: hook, beats, ending. "
    "Include on-screen text callouts. Return only the script, no preamble."
)

_SYSTEM_CONTENT_CAPTION = (
    "You are an Instagram copywriter. Write a caption for this post following the outline and "
    "direction. Include a hook line, body, and CTA. Use tasteful line breaks. Return only the caption text."
)

_SYSTEM_CONTENT_CAROUSEL = (
    "You are an Instagram carousel writer. Write slide-by-slide copy following the outline. "
    "Format as:\nSlide 1: <headline>\n<body>\n\nSlide 2: ...\n"
    "Keep each slide tight. Return only the slides text."
)

_SYSTEM_REWRITE = (
    "You are a top-tier editor. Rewrite the provided content applying the user's instruction while "
    "preserving the creator's voice. Return only the rewritten text, no preamble."
)

_SYSTEM_IMPROVE_HOOK = (
    "You are a hook doctor. Rewrite ONLY the opening hook (first 1-3 sentences or first slide) to "
    "be sharper, more curious, and more specific — everything else stays intact. Return the FULL "
    "updated content."
)

_SYSTEM_CRITIQUE = (
    "You are a rigorous script/copy editor. Critique the provided content against the project brief "
    "and selected direction. Return only valid JSON."
)

_SYSTEM_ASSISTANT = (
    "You are the AI assistant inside a specific creator's Project Workspace. You know only what's "
    "in the provided PROJECT CONTEXT. Answer concretely and briefly (under 220 words). If context "
    "is missing, say what's missing — don't invent details."
)


def _session(project_id: str, task: str) -> str:
    return f"proj-{project_id}-{task}"


async def run_research(
    context: ProjectContext, question: str,
) -> ResearchOutput:
    ctx = context.render()
    user = (
        f"{ctx}\n\n"
        f"## RESEARCH QUESTION\n{question.strip()}\n\n"
        "Task: produce a structured research brief for this project. "
        "Ground yourself ONLY in the sources and context above; if the sources are thin, say so in "
        "open_questions and suggest concrete follow-ups.\n\n"
        "Return JSON: {\n"
        '  "summary": "3-5 sentences",\n'
        '  "key_facts": ["bullet", ...],\n'
        '  "insights": ["bullet", ...],\n'
        '  "perspectives": ["bullet", ...],\n'
        '  "opportunities": ["bullet", ...],\n'
        '  "open_questions": ["bullet", ...]\n'
        "}"
    )
    return await call_structured(
        _SYSTEM_RESEARCH, user, _session(context.project.id, "research"),
        schema=ResearchOutput,
    )


async def run_directions(context: ProjectContext) -> DirectionsOutput:
    ctx = context.render()
    user = (
        f"{ctx}\n\n"
        "Task: propose 2-3 DISTINCT creative directions for this project. "
        "Return JSON: {\"directions\": [ {\"angle\": \"...\", \"audience_takeaway\": \"...\", "
        "\"format\": \"...\", \"tone\": \"...\", \"why_it_works\": \"...\"} ]}"
    )
    return await call_structured(
        _SYSTEM_DIRECTIONS, user, _session(context.project.id, "directions"),
        schema=DirectionsOutput,
    )


def _outline_system_for(content_type: str) -> str:
    return {
        "youtube_video": _SYSTEM_OUTLINE_YOUTUBE,
        "instagram_reel": _SYSTEM_OUTLINE_REEL,
        "instagram_post": _SYSTEM_OUTLINE_POST,
        "instagram_carousel": _SYSTEM_OUTLINE_CAROUSEL,
    }.get(content_type, _SYSTEM_OUTLINE_YOUTUBE)


async def run_outline(context: ProjectContext) -> OutlineOutput:
    ct = context.project.content_type.value if hasattr(context.project.content_type, "value") else context.project.content_type
    user = (
        f"{context.render()}\n\n"
        "Task: build the outline as JSON: {\"outline\": [ {\"label\": \"HOOK\", \"beats\": [\"...\"]}, ... ]}. "
        "Every section needs a short label and 1-6 beats. Match the project's selected direction."
    )
    return await call_structured(
        _outline_system_for(ct), user, _session(context.project.id, f"outline-{ct}"),
        schema=OutlineOutput,
    )


def _content_system_for(content_type: str) -> tuple[str, str]:
    """Returns (system_prompt, output_creative_type)."""
    return {
        "youtube_video":      (_SYSTEM_CONTENT_YOUTUBE, "script"),
        "instagram_reel":     (_SYSTEM_CONTENT_REEL_SCRIPT, "script"),
        "instagram_post":     (_SYSTEM_CONTENT_CAPTION, "caption"),
        "instagram_carousel": (_SYSTEM_CONTENT_CAROUSEL, "carousel"),
    }.get(content_type, (_SYSTEM_CONTENT_YOUTUBE, "script"))


async def run_content(context: ProjectContext) -> tuple[str, str]:
    """Returns (generated_text, output_creative_type)."""
    ct = context.project.content_type.value if hasattr(context.project.content_type, "value") else context.project.content_type
    system, out_type = _content_system_for(ct)
    user = f"{context.render()}\n\nWrite the content now."
    text = await call_text(system, user, _session(context.project.id, f"content-{ct}"))
    return text.strip(), out_type


async def run_edit(context: ProjectContext, *, action: str, content: str, instruction: str = "") -> str:
    """Return proposed replacement text. Caller decides whether to accept."""
    ct = context.project.content_type.value if hasattr(context.project.content_type, "value") else context.project.content_type
    if action == "rewrite":
        system = _SYSTEM_REWRITE
        user = (
            f"{context.render(include_content_objects=False)}\n\n"
            f"## INSTRUCTION\n{instruction or 'Rewrite for clarity and voice.'}\n\n"
            f"## CONTENT TO REWRITE\n{content}"
        )
    elif action == "improve_hook":
        system = _SYSTEM_IMPROVE_HOOK
        user = (
            f"{context.render(include_content_objects=False)}\n\n"
            f"## CURRENT CONTENT (return the FULL updated version, hook improved only)\n{content}"
        )
    else:
        raise AppError(Codes.INVALID_INPUT, "Unknown edit action", status_code=400)
    return (await call_text(system, user, _session(context.project.id, f"edit-{action}"))).strip()


async def run_critique(context: ProjectContext, content: str) -> CritiqueOutput:
    user = (
        f"{context.render(include_content_objects=False)}\n\n"
        f"## CONTENT TO CRITIQUE\n{content}\n\n"
        "Return JSON: {\"strengths\": [\"...\"], \"weaknesses\": [\"...\"], \"suggestions\": [\"...\"]}"
    )
    return await call_structured(
        _SYSTEM_CRITIQUE, user, _session(context.project.id, "critique"),
        schema=CritiqueOutput,
    )


async def run_assistant_reply(context: ProjectContext, history: List[dict], user_msg: str) -> str:
    """history: list of {role, content}. Returns assistant reply text."""
    convo = ""
    for m in history[-10:]:  # last 10 turns
        convo += f"[{m['role'].upper()}]: {_truncate(m['content'], 800)}\n"
    user = (
        f"{context.render()}\n\n"
        f"## RECENT CONVERSATION\n{convo}\n"
        f"[USER]: {user_msg}\n[ASSISTANT]:"
    )
    return (await call_text(_SYSTEM_ASSISTANT, user, _session(context.project.id, "chat"))).strip()
