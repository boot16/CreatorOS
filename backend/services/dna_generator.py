"""Generate an initial Creator DNA from onboarding input.

Reuses services/llm.py structured output. Persists via DNARepo. Never fabricates
historical performance — the DNA is flagged as 'initial' with confidence='initial'.
"""
from typing import List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from services.llm import call_structured
from repositories import DNARepo
from models.domain import CreatorDNASnapshot, DNAStatus


class _AudienceOut(BaseModel):
    description: str = ""
    interests: List[str] = Field(default_factory=list, max_length=10)
    experience_level: str = ""


class _VoiceOut(BaseModel):
    tone: List[str] = Field(default_factory=list, max_length=6)
    characteristics: List[str] = Field(default_factory=list, max_length=6)
    style_notes: str = ""


class InitialDNAOutput(BaseModel):
    creator_types: List[str] = Field(default_factory=list, max_length=6)
    topics: List[str] = Field(default_factory=list, max_length=12)
    subtopics: List[str] = Field(default_factory=list, max_length=12)
    content_pillars: List[str] = Field(default_factory=list, max_length=8)
    audience: _AudienceOut = Field(default_factory=_AudienceOut)
    platforms: List[str] = Field(default_factory=list, max_length=6)
    preferred_formats: List[str] = Field(default_factory=list, max_length=8)
    voice: _VoiceOut = Field(default_factory=_VoiceOut)
    goals: List[str] = Field(default_factory=list, max_length=8)
    constraints: List[str] = Field(default_factory=list, max_length=6)


_SYSTEM = (
    "You are helping a creator articulate their creative DNA from their own words. "
    "Extract STRUCTURED signals from what they told you. Do NOT invent historical performance. "
    "Do NOT invent audience size or metrics. Do NOT choose platforms they didn't mention. "
    "If they mentioned zero content, keep pillars/formats aspirational and short. Return only valid JSON."
)


async def generate_initial_dna(
    db, creator_id: str,
    *,
    creator_types: List[str],
    onboarding_text: str,
    topics: Optional[List[str]] = None,
    intended_audience: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    preferred_formats: Optional[List[str]] = None,
    goals: Optional[List[str]] = None,
    connected_sources: Optional[List[str]] = None,
) -> CreatorDNASnapshot:
    """Generate initial DNA and persist as a CreatorDNASnapshot. Idempotent per creator —
    creates a new snapshot each call so history is preserved."""
    lines = [
        f"CREATOR TYPES they selected: {', '.join(creator_types) or '(none)'}",
        f"WHAT THEY WROTE:\n\"\"\"{(onboarding_text or '').strip()[:6000]}\"\"\"",
    ]
    if topics:                  lines.append(f"Topics they mentioned: {', '.join(topics)}")
    if intended_audience:        lines.append(f"Intended audience: {intended_audience[:500]}")
    if platforms:                lines.append(f"Platforms they mentioned: {', '.join(platforms)}")
    if preferred_formats:        lines.append(f"Preferred formats: {', '.join(preferred_formats)}")
    if goals:                    lines.append(f"Goals: {', '.join(goals)}")
    if connected_sources:        lines.append(f"Existing public profiles: {', '.join(connected_sources[:5])}")
    lines.append(
        "\nReturn JSON:\n"
        "{\n"
        '  "creator_types": ["youtuber","educator",...],\n'
        '  "topics": ["short topic",...],\n'
        '  "subtopics": ["specific angle",...],\n'
        '  "content_pillars": ["3-5 content pillars"],\n'
        '  "audience": {"description":"1-2 sentences","interests":["..."],"experience_level":"beginner|intermediate|advanced|mixed"},\n'
        '  "platforms": ["youtube","instagram",...],\n'
        '  "preferred_formats": ["experiment","tutorial","story",...],\n'
        '  "voice": {"tone":["direct","curious"],"characteristics":["first-person","practical"],"style_notes":"1 sentence"},\n'
        '  "goals": ["grow","monetize",...],\n'
        '  "constraints": ["short constraints they mentioned"]\n'
        "}"
    )
    user = "\n".join(lines)
    parsed: InitialDNAOutput = await call_structured(
        _SYSTEM, user, session_id=f"initial-dna-{creator_id}",
        schema=InitialDNAOutput,
    )
    d = parsed.model_dump()

    now = datetime.now(timezone.utc).isoformat()
    snap = CreatorDNASnapshot(
        creator_id=creator_id,
        version=1,
        status=DNAStatus.ready,
        topic_dna={"topics": d["topics"], "subtopics": d["subtopics"], "content_pillars": d["content_pillars"]},
        format_dna={"preferred_formats": d["preferred_formats"]},
        creative_dna={
            "creator_types": d["creator_types"],
            "platforms": d["platforms"],
            "voice": d["voice"],
            "goals": d["goals"],
            "constraints": d["constraints"],
            "confidence": "initial",
            "source": "onboarding",
            "connected_sources": connected_sources or [],
        },
        audience_dna=d["audience"],
        performance_dna=None,  # explicit — no fabricated historical data
        computed_at=now,
        pipeline_version="m4-onboarding-v1",
    )
    await db.creator_dna_snapshots.insert_one(snap.model_dump())
    return snap
