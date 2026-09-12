"""M5-specific domain extensions kept isolated while the legacy project model remains stable."""
from typing import Literal

from pydantic import Field

from models.domain import CreativeDirection, _uid, _now


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
