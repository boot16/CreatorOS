"""DNA-01 domain models — extend the Phase 1 domain module.

- VideoContentAnalysis: per-video LLM interpretation (cached by source_content_hash)
- Evidence-carrying value types used inside CreatorDNASnapshot dimensions
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any
from pydantic import BaseModel, Field


def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _uid() -> str: return str(uuid.uuid4())


class VideoContentAnalysis(BaseModel):
    id: str = Field(default_factory=_uid)
    creator_id: str
    creator_video_id: str

    topics: List[str] = Field(default_factory=list)          # normalized topic slugs
    subtopics: List[str] = Field(default_factory=list)

    format: Optional[str] = None                              # canonical format enum
    format_secondary: Optional[str] = None

    hook_type: Optional[str] = None
    tone: Optional[str] = None
    storytelling_structure: Optional[str] = None
    presentation_style: Optional[str] = None

    audience_intent: Optional[str] = None
    content_promise: Optional[str] = None

    entities: List[str] = Field(default_factory=list)

    inference_confidence: float = 0.5                         # LLM-provided, [0,1]
    source_content_hash: str = ""
    model: str = ""
    prompt_version: str = "1.0"
    pipeline_version: str = "1.0"
    status: str = "success"                                    # success | failed | skipped
    error_message: Optional[str] = None

    created_at: str = Field(default_factory=_now)
