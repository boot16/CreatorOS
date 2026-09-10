"""Domain entity Pydantic models. Persisted with `id` (UUID) not Mongo `_id`."""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


# ---- Identity ----
class User(BaseModel):
    id: str = Field(default_factory=_uid)
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    google_sub: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class Workspace(BaseModel):
    id: str = Field(default_factory=_uid)
    owner_user_id: str
    name: str
    slug: str
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class WorkspaceRole(str, Enum):
    owner = "owner"
    member = "member"


class WorkspaceMember(BaseModel):
    id: str = Field(default_factory=_uid)
    workspace_id: str
    user_id: str
    role: WorkspaceRole = WorkspaceRole.owner
    status: str = "active"
    created_at: str = Field(default_factory=_now)


class Creator(BaseModel):
    id: str = Field(default_factory=_uid)
    workspace_id: str
    user_id: str
    display_name: str
    handle: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    primary_niche: Optional[str] = None
    country: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ---- Platform connection ----
class PlatformName(str, Enum):
    youtube = "youtube"


class ConnectionStatus(str, Enum):
    connected = "connected"
    disconnected = "disconnected"
    error = "error"


class ConnectedPlatform(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    platform: PlatformName
    external_account_id: str  # e.g. Google `sub`
    external_channel_id: Optional[str] = None
    display_name: Optional[str] = None
    handle: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    connection_status: ConnectionStatus = ConnectionStatus.connected
    connected_at: str = Field(default_factory=_now)
    last_synced_at: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class PlatformCredential(BaseModel):
    """OAuth tokens are stored ENCRYPTED, separate from the domain platform document."""
    id: str = Field(default_factory=_uid)
    connected_platform_id: str
    encrypted_access_token: Optional[str] = None
    encrypted_refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=_now)


# ---- YouTube source snapshots ----
class YouTubeChannelSnapshot(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    connected_platform_id: str
    channel_id: str
    title: str
    description: str = ""
    subscriber_count: int = 0
    view_count: int = 0
    video_count: int = 0
    captured_at: str = Field(default_factory=_now)
    source: str = "youtube_api"


class CreatorVideo(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    connected_platform_id: str
    external_video_id: str
    title: str
    description: str = ""
    thumbnail_url: Optional[str] = None
    published_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class VideoMetricSnapshot(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_video_id: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    captured_at: str = Field(default_factory=_now)
    source: str = "youtube_api"


# ---- Creator intent ----
class ExperimentationLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CreatorIntent(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    primary_goal: Optional[str] = None
    secondary_goals: List[str] = Field(default_factory=list)
    desired_topics: List[str] = Field(default_factory=list)
    topics_to_avoid: List[str] = Field(default_factory=list)
    formats_to_explore: List[str] = Field(default_factory=list)
    target_audience: Optional[str] = None
    experimentation_level: ExperimentationLevel = ExperimentationLevel.medium
    collaboration_goals: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ---- Creator DNA (schema only — not populated yet) ----
class DNAStatus(str, Enum):
    not_computed = "not_computed"
    insufficient_data = "insufficient_data"
    computing = "computing"
    ready = "ready"
    error = "error"


class Classification(str, Enum):
    OBSERVED = "OBSERVED"
    CALCULATED = "CALCULATED"
    INFERRED = "INFERRED"
    USER_PROVIDED = "USER_PROVIDED"


class CreatorDNASnapshot(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    version: int = 1
    status: DNAStatus = DNAStatus.not_computed
    topic_dna: Optional[dict] = None
    format_dna: Optional[dict] = None
    creative_dna: Optional[dict] = None
    audience_dna: Optional[dict] = None
    performance_dna: Optional[dict] = None
    evolution_dna: Optional[dict] = None
    source_snapshot_ids: List[str] = Field(default_factory=list)
    computed_at: Optional[str] = None
    pipeline_version: Optional[str] = None
    created_at: str = Field(default_factory=_now)


# ---- Session ----
class Session(BaseModel):
    sid: str
    user_id: str
    expires_at: str
    email: Optional[str] = None
    name: Optional[str] = None
    created_at: str = Field(default_factory=_now)


# ---- Projects (M2) ----
class ProjectContentType(str, Enum):
    youtube_video = "youtube_video"
    instagram_reel = "instagram_reel"
    instagram_post = "instagram_post"
    instagram_carousel = "instagram_carousel"


class ProjectPlatform(str, Enum):
    youtube = "youtube"
    instagram = "instagram"


class ProjectStatus(str, Enum):
    idea = "idea"
    researching = "researching"
    developing = "developing"
    writing = "writing"
    ready = "ready"
    shipped = "shipped"
    discarded = "discarded"


class ProjectBrief(BaseModel):
    topic: Optional[str] = None
    objective: Optional[str] = None
    target_audience: Optional[str] = None
    content_format: Optional[str] = None
    takeaway: Optional[str] = None
    working_title: Optional[str] = None


class Project(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    workspace_id: str
    title: str
    content_type: ProjectContentType
    platform: ProjectPlatform
    objective: Optional[str] = None
    status: ProjectStatus = ProjectStatus.idea
    brief: ProjectBrief = Field(default_factory=ProjectBrief)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class CreativeObjectType(str, Enum):
    notes = "notes"
    outline = "outline"
    script = "script"
    caption = "caption"
    carousel = "carousel"
    research = "research"
    direction = "direction"


class CreativeObject(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str
    type: CreativeObjectType
    title: Optional[str] = None
    content: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ProjectSource(BaseModel):
    """M3: research sources attached to a Project (user-provided URLs or pasted text)."""
    id: str = Field(default_factory=_uid)
    project_id: str
    title: str
    url: Optional[str] = None
    source_type: str = "url"  # url | text
    content: str = ""  # extracted/pasted content or short summary
    created_at: str = Field(default_factory=_now)


class ProjectChatMessage(BaseModel):
    """M3: assistant messages scoped to a project."""
    id: str = Field(default_factory=_uid)
    project_id: str
    creator_id: str
    role: str  # user | assistant
    content: str
    created_at: str = Field(default_factory=_now)


class ActivityEvent(BaseModel):
    id: str = Field(default_factory=_uid)
    project_id: str
    creator_id: str
    event_type: str
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)


class CreatorLearnedPrefs(BaseModel):
    """A compact behavioral profile, updated incrementally from creator signals."""
    creator_id: str
    likes: List[str] = Field(default_factory=list)
    dislikes: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    performance_notes: List[str] = Field(default_factory=list)
    signal_count: int = 0
    last_event_at: Optional[str] = None
    version: int = 1
    updated_at: str = Field(default_factory=_now)


# ---- Versioned LLM cache ----
class LLMCacheEntry(BaseModel):
    id: str = Field(default_factory=_uid)
    cache_kind: str
    entity_id: str
    entity_version: int = 1
    data_version: int = 1
    prompt_version: int = 1
    model: str
    key_hash: str  # sha256 of composite key
    value: Any
    created_at: str = Field(default_factory=_now)
    expires_at: Optional[str] = None
