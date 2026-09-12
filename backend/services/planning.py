"""M5.1 medium-aware planning.

CreatorOS owns the planning schema deterministically. The LLM fills a known Reel
specification; it does not decide what fields a production plan should contain.
"""
from pydantic import BaseModel, Field

from models.m5 import PlanningRequirement, ReelCreativePlan, ReelPlanBeat, CreativeDirectionV2, DirectionReadiness
from services.llm import call_structured


_REQUIREMENTS = {
    "instagram_reel": [
        PlanningRequirement(key="duration", label="Duration", description="Target running time and pacing envelope.", category="format"),
        PlanningRequirement(key="objective", label="Objective", description="What this Reel is intended to achieve.", category="strategy"),
        PlanningRequirement(key="audience_takeaway", label="Audience takeaway", description="What the viewer should think, feel, or understand by the end.", category="strategy"),
        PlanningRequirement(key="hook_strategy", label="Hook strategy", description="How the opening earns attention while serving the selected direction.", category="narrative"),
        PlanningRequirement(key="narrative_arc", label="Narrative arc", description="How the argument/story moves from opening tension to payoff.", category="narrative"),
        PlanningRequirement(key="beats", label="Timed beats", description="Time-bounded sequence of narrative and production beats.", category="production"),
        PlanningRequirement(key="spoken_audio", label="Spoken/audio", description="Dialogue, voiceover, silence, music or sound cue required per beat.", category="production"),
        PlanningRequirement(key="visual", label="Visual treatment", description="What the audience sees during each beat.", category="production"),
        PlanningRequirement(key="shot_framing", label="Shot/framing", description="Camera/framing instruction for each beat.", category="production"),
        PlanningRequirement(key="on_screen_text", label="On-screen text", description="Text overlays needed per beat.", category="production"),
        PlanningRequirement(key="transitions", label="Transitions", description="How beats connect visually or narratively.", category="production"),
        PlanningRequirement(key="assets", label="Assets", description="B-roll, graphics, screenshots, props or other assets required.", category="production"),
        PlanningRequirement(key="evidence", label="Evidence", description="Claims/examples requiring support before final creation.", category="research"),
        PlanningRequirement(key="cta", label="Ending / CTA", description="Closing payoff or action aligned with the objective.", category="narrative"),
    ]
}


def requirements_for(content_type: str) -> list[PlanningRequirement]:
    return list(_REQUIREMENTS.get(content_type, []))


class ReelPlanOutput(BaseModel):
    duration_seconds: int = Field(ge=10, le=180)
    objective: str
    audience_takeaway: str
    hook_strategy: str
    narrative_arc: str
    tone: str
    cta: str = ""
    beats: list[ReelPlanBeat] = Field(min_length=2, max_length=20)
    required_assets: list[str] = Field(default_factory=list, max_length=20)
    research_requirements: list[str] = Field(default_factory=list, max_length=10)
    unresolved_decisions: list[str] = Field(default_factory=list, max_length=8)


_SYSTEM = """You are the production-planning layer inside CreatorOS.
Turn the selected creative direction into an execution-ready Instagram Reel specification.
Do not write a generic outline. Plan the actual content beat-by-beat with timing, spoken/audio,
visual treatment, shot/framing, text, assets and evidence needs.
Do not fabricate research, sources, statistics, or proof. If a claim requires support, put it
in evidence_requirements/research_requirements. Preserve unresolved creator decisions instead
of silently inventing them. Return only valid JSON matching the requested schema."""


def _direction_block(direction: CreativeDirectionV2) -> str:
    return f"""SELECTED DIRECTION
Title: {direction.title}
Premise: {direction.premise}
Angle: {direction.angle}
Audience promise: {direction.audience_promise}
Creative treatment: {direction.creative_treatment}
Narrative shape: {direction.narrative_shape}
Emotional movement: {direction.emotional_movement or ''}
Format fit: {direction.format_fit}
Risks: {direction.risks}
Unresolved questions: {direction.unresolved_questions}"""


async def generate_reel_plan(project, direction: CreativeDirectionV2, readiness: DirectionReadiness | None) -> ReelCreativePlan:
    brief = project.brief.model_dump() if hasattr(project.brief, "model_dump") else dict(project.brief or {})
    readiness_block = "No readiness assessment available."
    if readiness:
        readiness_block = (
            f"Overall: {readiness.overall_status}\n"
            f"Criteria: {[c.model_dump() for c in readiness.criteria]}\n"
            f"Blocking questions: {readiness.blocking_questions}\n"
            f"Research needs: {readiness.research_needs}\n"
            f"Planning notes: {readiness.planning_notes}"
        )

    prompt = f"""PROJECT
Title: {project.title}
Objective: {project.objective or ''}
Brief: {brief}

{_direction_block(direction)}

READINESS
{readiness_block}

Create one production-ready Reel plan.
Rules:
- Prefer 30-60 seconds unless the project context clearly needs another duration.
- Beat timings must be chronological, non-overlapping, and fit inside duration_seconds.
- Each beat must have a clear narrative purpose.
- spoken_audio is what is said/heard, not a summary.
- visual and shot_framing must be concrete enough to execute.
- Put unsupported factual needs in evidence_requirements/research_requirements.
- Do not hide unresolved creator choices; include them in unresolved_decisions.
- The final beat should deliver the intended payoff or CTA.
"""
    result = await call_structured(
        _SYSTEM,
        prompt,
        session_id=f"proj-{project.id}-reel-plan-{direction.id}-r{direction.revision}",
        schema=ReelPlanOutput,
    )

    beats = sorted(result.beats, key=lambda b: (b.start_second, b.end_second))
    safe_beats: list[ReelPlanBeat] = []
    previous_end = 0
    for beat in beats:
        start = max(beat.start_second, previous_end)
        end = max(beat.end_second, start + 1)
        end = min(end, result.duration_seconds)
        if start >= result.duration_seconds:
            continue
        safe_beats.append(beat.model_copy(update={"start_second": start, "end_second": end}))
        previous_end = end

    if len(safe_beats) < 2:
        safe_beats = beats[:2]

    return ReelCreativePlan(
        project_id=project.id,
        creator_id=project.creator_id,
        direction_id=direction.id,
        direction_revision=direction.revision,
        duration_seconds=result.duration_seconds,
        objective=result.objective.strip(),
        audience_takeaway=result.audience_takeaway.strip(),
        hook_strategy=result.hook_strategy.strip(),
        narrative_arc=result.narrative_arc.strip(),
        tone=result.tone.strip(),
        cta=result.cta.strip(),
        beats=safe_beats,
        required_assets=[x.strip() for x in result.required_assets if x.strip()],
        research_requirements=[x.strip() for x in result.research_requirements if x.strip()],
        unresolved_decisions=[x.strip() for x in result.unresolved_decisions if x.strip()],
    )
