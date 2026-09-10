"""Incremental, best-effort folding of creator activity into a compact profile."""
from typing import List, Optional

from pydantic import BaseModel, Field

from models.domain import CreatorLearnedPrefs
from repositories import ActivityEventRepo, LearnedPrefsRepo
from services.llm import call_structured

MIN_NEW_EVENTS_TO_FOLD = 3


class _FoldedPrefs(BaseModel):
    likes: List[str] = Field(default_factory=list)
    dislikes: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    performance_notes: List[str] = Field(default_factory=list)


def _render_events(events) -> str:
    lines = []
    for event in events:
        metadata = event.metadata or {}
        if event.event_type == "creative_object_updated":
            lines.append(f"- creator edited fields: {metadata.get('fields', ['content'])}")
        elif event.event_type == "ai_proposal_feedback":
            note = f" (note: {metadata['reason'][:120]})" if metadata.get("reason") else ""
            lines.append(f"- creator {metadata.get('action', 'responded to')} an AI {metadata.get('kind', 'proposal')}{note}")
        elif event.event_type == "project_status_changed" and metadata.get("status") == "shipped":
            lines.append("- a project reached SHIPPED status")
        elif event.event_type in {"direction_selected", "research_generated", "outline_generated", "content_generated"}:
            angle = f": {metadata['angle'][:120]}" if metadata.get("angle") else ""
            lines.append(f"- {event.event_type.replace('_', ' ')}{angle}")
    return "\n".join(lines) if lines else "(no notable signals)"


async def maybe_fold_in(db, creator_id: str, force: bool = False) -> Optional[CreatorLearnedPrefs]:
    """Update from only activity since the last fold; failures leave existing data intact."""
    prefs_repo = LearnedPrefsRepo(db)
    existing = await prefs_repo.get(creator_id)
    events = await ActivityEventRepo(db).list_for_creator(
        creator_id, since=existing.last_event_at if existing else None,
    )
    if not events or (not force and len(events) < MIN_NEW_EVENTS_TO_FOLD):
        return existing

    current = existing or CreatorLearnedPrefs(creator_id=creator_id)
    system = (
        "Maintain a compact behavioral profile for a content creator using an AI writing tool. "
        "Use the current profile and new signals to return an updated profile. Preserve still-valid "
        "items, add only supported insights, and remove contradictions. Keep every list under eight "
        "short, specific, actionable entries. Do not infer a preference from weak evidence. "
        "Return only JSON matching the schema."
    )
    user = (
        f"## CURRENT PROFILE\nlikes: {current.likes}\ndislikes: {current.dislikes}\n"
        f"patterns: {current.patterns}\nperformance_notes: {current.performance_notes}\n\n"
        f"## NEW SIGNALS\n{_render_events(events)}"
    )
    try:
        folded = await call_structured(system, user, f"learned-prefs-{creator_id}", schema=_FoldedPrefs)
    except Exception:
        return existing

    updated = CreatorLearnedPrefs(
        creator_id=creator_id,
        likes=folded.likes[:8], dislikes=folded.dislikes[:8], patterns=folded.patterns[:8],
        performance_notes=folded.performance_notes[:8],
        signal_count=current.signal_count + len(events), last_event_at=events[-1].created_at,
        version=current.version + 1,
    )
    return await prefs_repo.upsert(updated)
