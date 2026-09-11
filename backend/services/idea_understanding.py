"""M5.1 idea-understanding reasoning.

This service converts a raw creator thought into structured project state. It does not
persist anything and it does not invent external facts. Persistence/origin assignment is
owned by the caller so AI inference can never be confused with creator-confirmed input.
"""
from typing import Optional

from pydantic import BaseModel, Field

from models.domain import IdeaUnderstanding, IdeaUnderstandingField
from services.llm import call_structured


class IdeaUnderstandingOutput(BaseModel):
    subject: Optional[str] = None
    creator_perspective: Optional[str] = None
    core_claim: Optional[str] = None
    intent: Optional[str] = None
    target_audience: Optional[str] = None
    desired_effect: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    open_questions: list[str] = Field(default_factory=list, max_length=6)
    material_unknowns: list[str] = Field(default_factory=list, max_length=6)
    confidence: dict[str, float] = Field(default_factory=dict)


_SYSTEM = """You are the idea-understanding layer inside CreatorOS.
Your job is to understand what the creator means before any creative direction is generated.
Use only the creator's raw idea and the supplied project metadata. Do not add outside facts.
Separate what is directly expressed from what must be inferred. Keep claims faithful to the
creator's meaning rather than making them stronger or more sensational. If information that
could materially change the creative direction is missing, put it in material_unknowns.
Open questions should be useful, specific, and minimal. Return only valid JSON."""


def _clean_list(items: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in items or []:
        text = (item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _confidence(result: IdeaUnderstandingOutput, name: str) -> Optional[float]:
    value = result.confidence.get(name)
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def build_understanding(project, raw_idea: str, result: IdeaUnderstandingOutput) -> IdeaUnderstanding:
    """Map AI output to canonical state. Every AI-extracted field starts as inferred."""
    return IdeaUnderstanding(
        project_id=project.id,
        creator_id=project.creator_id,
        raw_idea=raw_idea.strip(),
        subject=IdeaUnderstandingField(value=result.subject, origin="inferred", confidence=_confidence(result, "subject")),
        creator_perspective=IdeaUnderstandingField(value=result.creator_perspective, origin="inferred", confidence=_confidence(result, "creator_perspective")),
        core_claim=IdeaUnderstandingField(value=result.core_claim, origin="inferred", confidence=_confidence(result, "core_claim")),
        intent=IdeaUnderstandingField(value=result.intent, origin="inferred", confidence=_confidence(result, "intent")),
        target_audience=IdeaUnderstandingField(value=result.target_audience, origin="inferred", confidence=_confidence(result, "target_audience")),
        desired_effect=IdeaUnderstandingField(value=result.desired_effect, origin="inferred", confidence=_confidence(result, "desired_effect")),
        assumptions=_clean_list(result.assumptions, 8),
        open_questions=_clean_list(result.open_questions, 6),
        material_unknowns=_clean_list(result.material_unknowns, 6),
    )


async def understand_idea(project, raw_idea: str) -> IdeaUnderstanding:
    raw = raw_idea.strip()
    brief = project.brief.model_dump() if hasattr(project.brief, "model_dump") else dict(project.brief or {})
    metadata = {
        "title": project.title,
        "content_type": project.content_type.value if hasattr(project.content_type, "value") else project.content_type,
        "platform": project.platform.value if hasattr(project.platform, "value") else project.platform,
        "objective": project.objective,
        "brief": {k: v for k, v in brief.items() if v},
    }
    user = f"""PROJECT METADATA
{metadata}

CREATOR RAW IDEA
{raw}

Return JSON with these keys:
subject, creator_perspective, core_claim, intent, target_audience, desired_effect,
assumptions, open_questions, material_unknowns, confidence.

confidence must be an object whose keys are the six scalar fields and values are 0..1.
Do not ask questions merely because a field is blank. Only include material_unknowns when
answering them would plausibly change the direction, argument, audience, or execution."""
    result = await call_structured(
        _SYSTEM,
        user,
        session_id=f"proj-{project.id}-idea-understanding",
        schema=IdeaUnderstandingOutput,
    )
    return build_understanding(project, raw, result)
