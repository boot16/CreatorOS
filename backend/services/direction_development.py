"""M5.1 direction development: refine/combine selected treatments and assess readiness.

This service intentionally reasons over persisted creative state. It does not invent external
facts and it does not use a numeric 'quality score'. Readiness is expressed as concrete
resolved/unresolved planning criteria so the creator can act on it.
"""
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from models.m5 import CreativeDirectionV2, DirectionReadiness, DirectionReadinessCriterion
from services.llm import call_structured


class DirectionDraftOutput(BaseModel):
    title: str
    premise: str
    angle: str
    audience_promise: str
    creative_treatment: str
    narrative_shape: str
    emotional_movement: str = ""
    format_fit: str
    why_this_direction: str
    risks: list[str] = Field(default_factory=list, max_length=5)
    unresolved_questions: list[str] = Field(default_factory=list, max_length=5)


class ReadinessCriterionOutput(BaseModel):
    key: Literal[
        "core_idea",
        "audience_promise",
        "creator_perspective",
        "supporting_example",
        "evidence",
        "ending_payoff",
        "format_feasibility",
    ]
    status: Literal["ready", "needs_resolution"]
    note: str
    evidence_needed: bool = False


class DirectionReadinessOutput(BaseModel):
    overall_status: Literal["ready", "needs_work"]
    criteria: list[ReadinessCriterionOutput] = Field(min_length=7, max_length=7)
    blocking_questions: list[str] = Field(default_factory=list, max_length=4)
    research_needs: list[str] = Field(default_factory=list, max_length=5)
    planning_notes: list[str] = Field(default_factory=list, max_length=5)


_DIRECTION_SYSTEM = """You are the creative development layer inside CreatorOS.
You are editing a creator-selected creative treatment, not generating generic content.
Preserve the creator's underlying perspective. Make the requested change materially visible
in the creative mechanism, narrative logic, or viewer experience. Do not invent factual
evidence, statistics, sources, or creator history. Return only valid JSON."""

_READINESS_SYSTEM = """You are a rigorous creative producer inside CreatorOS.
Assess whether a selected creative direction is sufficiently resolved to enter production
planning. Do not score it numerically. Do not create fake blockers. Only mark something as
needs_resolution when it would materially change the resulting content or when a factual
claim genuinely needs evidence. Treat missing external evidence as a research need, not as
a reason to fabricate support. Return only valid JSON."""


def _clean(items: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        text = (item or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _direction_context(direction: CreativeDirectionV2) -> str:
    return f"""DIRECTION
Title: {direction.title}
Premise: {direction.premise}
Angle: {direction.angle}
Audience promise: {direction.audience_promise}
Creative treatment: {direction.creative_treatment}
Narrative shape: {direction.narrative_shape}
Emotional movement: {direction.emotional_movement or ''}
Format fit: {direction.format_fit}
Why this direction: {direction.why_this_direction}
Risks: {direction.risks}
Unresolved questions: {direction.unresolved_questions}"""


def _build_direction(project, source: CreativeDirectionV2, output: DirectionDraftOutput, *, parents: list[str]) -> CreativeDirectionV2:
    return CreativeDirectionV2(
        project_id=project.id,
        creator_id=project.creator_id,
        batch_id=str(uuid.uuid4()),
        source_understanding_version=source.source_understanding_version,
        revision=max(source.revision + 1, 2),
        parent_direction_ids=parents,
        title=output.title.strip(),
        premise=output.premise.strip(),
        angle=output.angle.strip(),
        audience_promise=output.audience_promise.strip(),
        creative_treatment=output.creative_treatment.strip(),
        narrative_shape=output.narrative_shape.strip(),
        emotional_movement=output.emotional_movement.strip() or None,
        format_fit=output.format_fit.strip(),
        why_this_direction=output.why_this_direction.strip(),
        risks=_clean(output.risks, 5),
        unresolved_questions=_clean(output.unresolved_questions, 5),
    )


async def refine_direction(project, direction: CreativeDirectionV2, instruction: str) -> CreativeDirectionV2:
    content_type = project.content_type.value if hasattr(project.content_type, "value") else project.content_type
    prompt = f"""PROJECT
Title: {project.title}
Content type: {content_type}
Objective: {project.objective or ''}

{_direction_context(direction)}

CREATOR REFINEMENT REQUEST
{instruction.strip()}

Return a revised direction with: title, premise, angle, audience_promise,
creative_treatment, narrative_shape, emotional_movement, format_fit,
why_this_direction, risks, unresolved_questions.

Do not turn this into a script. Keep it at creative-direction level."""
    result = await call_structured(
        _DIRECTION_SYSTEM,
        prompt,
        session_id=f"proj-{project.id}-direction-refine-{direction.id}",
        schema=DirectionDraftOutput,
    )
    return _build_direction(project, direction, result, parents=[direction.id])


async def combine_directions(project, primary: CreativeDirectionV2, secondary: CreativeDirectionV2, instruction: str = "") -> CreativeDirectionV2:
    content_type = project.content_type.value if hasattr(project.content_type, "value") else project.content_type
    prompt = f"""PROJECT
Title: {project.title}
Content type: {content_type}
Objective: {project.objective or ''}

PRIMARY / CURRENTLY SELECTED
{_direction_context(primary)}

SECONDARY DIRECTION TO BORROW FROM
{_direction_context(secondary)}

CREATOR NOTE
{instruction.strip() or 'Combine only the strongest compatible mechanisms. Do not create a vague average of both.'}

Create one coherent direction. The result must have a single premise and narrative logic,
not a list of features from two concepts. Return: title, premise, angle, audience_promise,
creative_treatment, narrative_shape, emotional_movement, format_fit, why_this_direction,
risks, unresolved_questions."""
    result = await call_structured(
        _DIRECTION_SYSTEM,
        prompt,
        session_id=f"proj-{project.id}-direction-combine-{primary.id}-{secondary.id}",
        schema=DirectionDraftOutput,
    )
    combined = _build_direction(project, primary, result, parents=[primary.id, secondary.id])
    combined.revision = max(primary.revision, secondary.revision) + 1
    return combined


async def assess_direction_readiness(project, direction: CreativeDirectionV2) -> DirectionReadiness:
    brief = project.brief.model_dump() if hasattr(project.brief, "model_dump") else dict(project.brief or {})
    content_type = project.content_type.value if hasattr(project.content_type, "value") else project.content_type
    prompt = f"""PROJECT
Title: {project.title}
Content type: {content_type}
Objective: {project.objective or ''}
Brief: {brief}

{_direction_context(direction)}

Assess exactly these seven criteria once each:
core_idea, audience_promise, creator_perspective, supporting_example, evidence,
ending_payoff, format_feasibility.

A criterion is ready if there is enough information to proceed into detailed creative
planning. It does not need final wording yet. Mark needs_resolution only for material gaps.
Return overall_status, criteria, blocking_questions, research_needs, planning_notes."""
    result = await call_structured(
        _READINESS_SYSTEM,
        prompt,
        session_id=f"proj-{project.id}-direction-readiness-{direction.id}-r{direction.revision}",
        schema=DirectionReadinessOutput,
    )

    expected = [
        "core_idea",
        "audience_promise",
        "creator_perspective",
        "supporting_example",
        "evidence",
        "ending_payoff",
        "format_feasibility",
    ]
    by_key = {item.key: item for item in result.criteria}
    criteria = []
    for key in expected:
        item = by_key.get(key)
        if item is None:
            criteria.append(DirectionReadinessCriterion(
                key=key,
                status="needs_resolution",
                note="Assessment did not resolve this criterion.",
            ))
        else:
            criteria.append(DirectionReadinessCriterion(
                key=item.key,
                status=item.status,
                note=item.note.strip(),
                evidence_needed=item.evidence_needed,
            ))

    computed_status = "ready" if all(c.status == "ready" for c in criteria) else "needs_work"
    return DirectionReadiness(
        project_id=project.id,
        creator_id=project.creator_id,
        direction_id=direction.id,
        direction_revision=direction.revision,
        overall_status=computed_status,
        criteria=criteria,
        blocking_questions=_clean(result.blocking_questions, 4),
        research_needs=_clean(result.research_needs, 5),
        planning_notes=_clean(result.planning_notes, 5),
    )
