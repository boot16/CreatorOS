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


# ---- M2: Project schemas ----
_CONTENT_TYPES = {"youtube_video", "instagram_reel", "instagram_post", "instagram_carousel"}
_STATUSES = {"idea", "researching", "developing", "writing", "ready", "shipped", "discarded"}
_CREATIVE_TYPES = {"notes", "outline", "script", "caption", "carousel", "research", "direction"}


class ProjectBriefBody(BaseModel):
    topic: Optional[str] = Field(default=None, max_length=2000)
    objective: Optional[str] = Field(default=None, max_length=2000)
    target_audience: Optional[str] = Field(default=None, max_length=2000)
    content_format: Optional[str] = Field(default=None, max_length=500)
    takeaway: Optional[str] = Field(default=None, max_length=2000)
    working_title: Optional[str] = Field(default=None, max_length=500)


class ProjectCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content_type: str
    objective: Optional[str] = Field(default=None, max_length=2000)


class ProjectUpdateBody(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    objective: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    creator_id: str
    workspace_id: str
    title: str
    content_type: str
    platform: str
    objective: Optional[str] = None
    status: str
    brief: ProjectBriefBody = Field(default_factory=ProjectBriefBody)
    created_at: str
    updated_at: str


class CreativeObjectBody(BaseModel):
    type: str
    title: Optional[str] = Field(default=None, max_length=500)
    content: str = Field(default="", max_length=100_000)


class CreativeObjectUpdateBody(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = Field(default=None, max_length=100_000)


class CreativeObjectResponse(BaseModel):
    id: str
    project_id: str
    type: str
    title: Optional[str] = None
    content: str
    created_at: str
    updated_at: str


class ActivityEventResponse(BaseModel):
    id: str
    project_id: str
    creator_id: str
    event_type: str
    metadata: dict = Field(default_factory=dict)
    created_at: str


# ---- M3: Project-Aware AI schemas ----
class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceBody(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    url: Optional[str] = Field(default=None, max_length=2000)
    source_type: str = Field(default="url")  # url | text
    content: str = Field(default="", max_length=20000)


class SourceResponse(BaseModel):
    id: str
    project_id: str
    title: str
    url: Optional[str] = None
    source_type: str
    content: str
    created_at: str


class DirectionSelectBody(BaseModel):
    angle: str = Field(min_length=1, max_length=500)
    audience_takeaway: str = Field(default="", max_length=2000)
    format: str = Field(default="", max_length=500)
    tone: str = Field(default="", max_length=500)
    why_it_works: str = Field(default="", max_length=2000)


class EditRequest(BaseModel):
    action: str  # rewrite | improve_hook | critique
    content: str = Field(min_length=1, max_length=100_000)
    instruction: Optional[str] = Field(default=None, max_length=2000)


class AiFeedbackBody(BaseModel):
    kind: str = Field(max_length=40)
    action: str
    reason: Optional[str] = Field(default=None, max_length=300)


class LearnedPrefsResponse(BaseModel):
    creator_id: str
    likes: List[str] = Field(default_factory=list)
    dislikes: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    performance_notes: List[str] = Field(default_factory=list)
    signal_count: int = 0
    updated_at: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageResponse(BaseModel):
    id: str
    project_id: str
    creator_id: str
    role: str
    content: str
    created_at: str
