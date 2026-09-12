"""M5-specific domain extensions kept isolated while the legacy project model remains stable."""
from typing import Literal, Optional, Any

from pydantic import BaseModel, Field

from models.domain import CreativeDirection, _uid, _now


class FoundationField(BaseModel):
    value: Optional[str] = None
    origin: Literal["creator_provided", "inferred", "confirmed", "learned"] = "inferred"
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ProjectFoundation(BaseModel):
    """Living project context shared by ideation, research and content execution."""
    id: str = Field(default_factory=_uid)
    project_id: str
    creator_id: str
    vision: FoundationField = Field(default_factory=FoundationField)
    context: FoundationField = Field(default_factory=FoundationField)
    goal: FoundationField = Field(default_factory=FoundationField)
    audience: FoundationField = Field(default_factory=FoundationField)
    creator_perspective: FoundationField = Field(default_factory=FoundationField)
    platform_format: FoundationField = Field(default_factory=FoundationField)
    constraints: list[str] = Field(default_factory=list)
    known_facts: list[str] = Field(default_factory=list)
    material_unknowns: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    version: int = 1
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class LearningSignal(BaseModel):
    """Evidence captured from creator behavior; raw evidence is preserved before inference."""
    id: str = Field(default_factory=_uid)
    creator_id: str
    project_id: Optional[str] = None
    signal_type: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    strength: Literal["weak", "medium", "strong", "very_strong"] = "medium"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class CreatorPreferenceEvidence(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    key: str
    scope: str = "global"
    hypothesis: str
    confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    evidence_count: int = 0
    counter_evidence_count: int = 0
    supporting_signal_ids: list[str] = Field(default_factory=list)
    last_seen_at: Optional[str] = None
    status: Literal["hypothesis", "active", "weakened"] = "hypothesis"
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class CreativeDirectionV2(CreativeDirection):
    """CreativeDirection with derivation metadata for refine/combine operations."""
    revision: int = Field(default=1, ge=1)
    parent_direction_ids: list[str] = Field(default_factory=list)


class DirectionReadinessCriterion(BaseModel):
    key: str
    status: Literal["ready", "needs_resolution"]
    note: str
    evidence_needed: bool = False


class DirectionReadiness(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str
    creator_id: str
    direction_id: str
    direction_revision: int = 1
    overall_status: Literal["ready", "needs_work"] = "needs_work"
    criteria: list[DirectionReadinessCriterion] = Field(default_factory=list)
    blocking_questions: list[str] = Field(default_factory=list)
    research_needs: list[str] = Field(default_factory=list)
    planning_notes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class PlanningRequirement(BaseModel):
    key: str
    label: str
    description: str
    required: bool = True
    category: str


class ReelPlanBeat(BaseModel):
    start_second: int = Field(ge=0)
    end_second: int = Field(gt=0)
    purpose: str
    spoken_audio: str
    visual: str
    shot_framing: str
    on_screen_text: str = ""
    transition: str = ""
    assets: list[str] = Field(default_factory=list)
    evidence_requirements: list[str] = Field(default_factory=list)


class ReelCreativePlan(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str
    creator_id: str
    direction_id: str
    direction_revision: int = 1
    version: int = 1
    format: Literal["instagram_reel"] = "instagram_reel"
    duration_seconds: int = Field(ge=10, le=180)
    objective: str
    audience_takeaway: str
    hook_strategy: str
    narrative_arc: str
    tone: str
    cta: str = ""
    beats: list[ReelPlanBeat] = Field(min_length=2, max_length=20)
    required_assets: list[str] = Field(default_factory=list)
    research_requirements: list[str] = Field(default_factory=list)
    unresolved_decisions: list[str] = Field(default_factory=list)
    status: Literal["draft", "approved"] = "draft"
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
