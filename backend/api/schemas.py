"""API response schemas — never return raw Mongo dicts."""
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class CurrentCreatorContext(BaseModel):
    is_authenticated: bool
    is_demo: bool
    data_mode: str
    user: Optional[dict] = None
    creator: Optional[dict] = None
    workspace: Optional[dict] = None
    youtube_connected: bool = False
    dna_status: str = "not_computed"


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str


class ConnectedPlatformResponse(BaseModel):
    id: str
    platform: str
    display_name: Optional[str]
    handle: Optional[str]
    connection_status: str
    last_synced_at: Optional[str]


class CreatorIntentBody(BaseModel):
    primary_goal: Optional[str] = None
    secondary_goals: List[str] = Field(default_factory=list, max_length=8)
    desired_topics: List[str] = Field(default_factory=list, max_length=20)
    topics_to_avoid: List[str] = Field(default_factory=list, max_length=20)
    formats_to_explore: List[str] = Field(default_factory=list, max_length=10)
    target_audience: Optional[str] = Field(default=None, max_length=500)
    experimentation_level: Optional[str] = None  # low|medium|high
    collaboration_goals: List[str] = Field(default_factory=list, max_length=8)


class CreatorIntentResponse(CreatorIntentBody):
    id: Optional[str] = None
    creator_id: Optional[str] = None
    updated_at: Optional[str] = None


class SyncResultResponse(BaseModel):
    creator_id: str
    videos_seen: int
    videos_created: int
    videos_updated: int
    snapshot_time: str
    status: str


class CreatorDNAStatusResponse(BaseModel):
    creator_id: Optional[str] = None
    status: str
    version: int = 0
    computed_at: Optional[str] = None


# ---- Structured LLM output schemas ----
class IdeaLabOutput(BaseModel):
    concept: str
    titles: List[str] = Field(min_length=3, max_length=6)
    hooks: List[str] = Field(min_length=2, max_length=5)
    structure: List[str] = Field(min_length=3, max_length=8)


class OppBulletsOutput(BaseModel):
    bullets: List[str] = Field(min_length=2, max_length=6)


class TrendExplanationOutput(BaseModel):
    why: str
    related: List[str] = Field(min_length=1, max_length=8)
    audience: str
