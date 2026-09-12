"""Generate meaningfully distinct creative directions from canonical idea understanding."""
import uuid
from pydantic import BaseModel, Field

from models.domain import IdeaUnderstanding
from models.m5 import CreativeDirectionV2
from services.llm import call_structured


class CreativeDirectionOption(BaseModel):
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


class CreativeDirectionsOutput(BaseModel):
    directions: list[CreativeDirectionOption] = Field(min_length=2, max_length=3)


_SYSTEM = """You are the creative-development layer inside CreatorOS.
Generate genuinely different ways to express the creator's already-understood idea.
Do not produce three hooks for the same treatment. Each direction must differ in its
creative mechanism, narrative logic, viewer experience, or evidence/story strategy.
Stay faithful to the creator's perspective. Do not invent external facts. If a direction
would need proof, examples, or context that is not present, name that in risks or unresolved_questions.
Return only valid JSON."""


def _field_value(understanding: IdeaUnderstanding, name: str) -> str:
    field = getattr(understanding, name)
    return (field.value or "").strip()


def _clean(items: list[str], limit: int = 5) -> list[str]:
    out = []
    seen = set()
    for item in items or []:
        text = (item or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append(text)
        if len(out) >= limit:
            break
    return out


async def generate_creative_directions(project, understanding: IdeaUnderstanding) -> list[CreativeDirectionV2]:
    content_type = project.content_type.value if hasattr(project.content_type, "value") else project.content_type
    prompt = f"""PROJECT
Title: {project.title}
Content type: {content_type}
Objective: {project.objective or ''}

UNDERSTOOD IDEA
Raw idea: {understanding.raw_idea}
Subject: {_field_value(understanding, 'subject')}
Creator perspective: {_field_value(understanding, 'creator_perspective')}
Core claim: {_field_value(understanding, 'core_claim')}
Intent: {_field_value(understanding, 'intent')}
Audience: {_field_value(understanding, 'target_audience')}
Desired effect: {_field_value(understanding, 'desired_effect')}
Material unknowns: {understanding.material_unknowns}
Assumptions: {understanding.assumptions}

Create 3 distinct creative directions. For each return:
title, premise, angle, audience_promise, creative_treatment, narrative_shape,
emotional_movement, format_fit, why_this_direction, risks, unresolved_questions.

The title is a short label for the direction, not a content headline.
creative_treatment explains how the idea would be experienced, not merely what it says.
narrative_shape describes the progression (for example argument, transformation, demonstration,
visual thought experiment, story, comparison) without forcing one of those examples."""

    result = await call_structured(
        _SYSTEM,
        prompt,
        session_id=f"proj-{project.id}-creative-directions-v2",
        schema=CreativeDirectionsOutput,
    )
    batch_id = str(uuid.uuid4())
    return [
        CreativeDirectionV2(
            project_id=project.id,
            creator_id=project.creator_id,
            batch_id=batch_id,
            source_understanding_version=understanding.version,
            title=option.title.strip(),
            premise=option.premise.strip(),
            angle=option.angle.strip(),
            audience_promise=option.audience_promise.strip(),
            creative_treatment=option.creative_treatment.strip(),
            narrative_shape=option.narrative_shape.strip(),
            emotional_movement=option.emotional_movement.strip() or None,
            format_fit=option.format_fit.strip(),
            why_this_direction=option.why_this_direction.strip(),
            risks=_clean(option.risks),
            unresolved_questions=_clean(option.unresolved_questions),
        )
        for option in result.directions
    ]
