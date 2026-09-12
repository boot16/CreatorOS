"""Build a living Project Foundation without forcing every creator thought into a thesis template."""
from typing import Optional, Literal

from pydantic import BaseModel, Field

from models.m5 import ProjectFoundation, FoundationField
from services.llm import call_structured


class FoundationOutput(BaseModel):
    starting_mode: Literal["idea", "needs_ideas", "opportunity", "execution"] = "idea"
    vision: Optional[str] = None
    context: Optional[str] = None
    goal: Optional[str] = None
    audience: Optional[str] = None
    creator_perspective: Optional[str] = None
    platform_format: Optional[str] = None
    constraints: list[str] = Field(default_factory=list, max_length=8)
    known_facts: list[str] = Field(default_factory=list, max_length=10)
    material_unknowns: list[str] = Field(default_factory=list, max_length=5)
    next_question: Optional[str] = None
    can_ideate_now: bool = False
    confidence: dict[str, float] = Field(default_factory=dict)


_SYSTEM = """You are the project-intake reasoning layer inside CreatorOS, a creative operating system.
Your job is to reduce creator work, not make the creator administer AI fields.
Classify how the creator is starting: they may already have a content idea, need ideas, be reacting to an opportunity, or already know what they want and need execution help.
Build only the context actually supported by the creator's words and project metadata. A request is not a creator perspective. A goal is not a core belief. Never manufacture a thesis, audience, positioning, or creative opinion.
If one missing fact would materially change the ideas or execution, put it first in material_unknowns and ask ONE concise next_question. Do not create a questionnaire.
Detect platform/format conflicts between the creator's words and project metadata and make that a material unknown.
can_ideate_now is true only when enough context exists to produce useful, non-generic creative directions.
Return valid JSON only."""


def _field(value, confidence, key):
    if not value:
        return FoundationField(value=None, origin="inferred", confidence=None)
    score = confidence.get(key)
    return FoundationField(value=value.strip(), origin="inferred", confidence=score)


async def build_project_foundation(project, creator_input: str) -> tuple[ProjectFoundation, FoundationOutput]:
    brief = project.brief.model_dump() if hasattr(project.brief, "model_dump") else dict(project.brief or {})
    metadata = {
        "title": project.title,
        "platform": project.platform.value if hasattr(project.platform, "value") else project.platform,
        "content_type": project.content_type.value if hasattr(project.content_type, "value") else project.content_type,
        "objective": project.objective,
        "existing_brief": {k: v for k, v in brief.items() if v},
    }
    result = await call_structured(
        _SYSTEM,
        f"PROJECT METADATA\n{metadata}\n\nCREATOR INPUT\n{creator_input.strip()}\n\nBuild the living project foundation.",
        session_id=f"proj-{project.id}-foundation",
        schema=FoundationOutput,
    )
    foundation = ProjectFoundation(
        project_id=project.id,
        creator_id=project.creator_id,
        vision=_field(result.vision, result.confidence, "vision"),
        context=_field(result.context, result.confidence, "context"),
        goal=_field(result.goal, result.confidence, "goal"),
        audience=_field(result.audience, result.confidence, "audience"),
        creator_perspective=_field(result.creator_perspective, result.confidence, "creator_perspective"),
        platform_format=_field(result.platform_format, result.confidence, "platform_format"),
        constraints=[x.strip() for x in result.constraints if x.strip()],
        known_facts=[x.strip() for x in result.known_facts if x.strip()],
        material_unknowns=[x.strip() for x in result.material_unknowns if x.strip()],
    )
    return foundation, result
