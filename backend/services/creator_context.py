"""Creator context service — the single source of truth for who the current creator is
and what CreatorOS knows about them. Consumed by AI features so Feed/Studio/IdeaLab/
Project-Assistant/Scripts all speak about THE SAME creator.
"""
from typing import Optional

from core.identity import CurrentUser
from repositories import CreatorRepo, DNARepo, IntentRepo, PlatformRepo


class CreatorContext:
    def __init__(self, creator: Optional[dict], dna: Optional[dict],
                 intent: Optional[dict], platforms: list, is_demo: bool):
        self.creator = creator
        self.dna = dna
        self.intent = intent
        self.platforms = platforms
        self.is_demo = is_demo

    def to_dict(self) -> dict:
        return {
            "creator": self.creator,
            "dna": self.dna,
            "intent": self.intent,
            "platforms": self.platforms,
            "is_demo": self.is_demo,
            "has_creator": self.creator is not None,
            "has_dna": self.dna is not None,
        }

    def render_for_prompt(self, max_chars: int = 2500) -> str:
        """Compact textual creator context injected into AI prompts."""
        if not self.creator and not self.dna:
            return ""
        lines = ["## CREATOR"]
        c = self.creator or {}
        if c.get("display_name") or c.get("name"):
            lines.append(f"- name: {c.get('display_name') or c.get('name')}")
        if c.get("handle"):
            lines.append(f"- handle: {c['handle']}")
        if c.get("primary_niche") or c.get("niche"):
            lines.append(f"- niche: {c.get('primary_niche') or c.get('niche')}")
        if c.get("bio"):
            lines.append(f"- bio: {c['bio'][:300]}")

        d = self.dna or {}
        if d:
            lines.append("\n## CREATOR DNA")
            for key in ("creator_types", "topics", "subtopics", "content_pillars",
                        "platforms", "preferred_formats", "goals", "constraints"):
                v = d.get(key)
                if isinstance(v, list) and v:
                    lines.append(f"- {key}: {', '.join(str(x) for x in v[:12])}")
            aud = d.get("audience") or {}
            if aud:
                if aud.get("description"):
                    lines.append(f"- audience: {aud['description'][:220]}")
                if aud.get("interests"):
                    lines.append(f"- audience_interests: {', '.join(aud['interests'][:8])}")
                if aud.get("experience_level"):
                    lines.append(f"- audience_experience: {aud['experience_level']}")
            voice = d.get("voice") or {}
            if voice:
                if voice.get("tone"):
                    lines.append(f"- tone: {', '.join(voice['tone']) if isinstance(voice['tone'], list) else voice['tone']}")
                if voice.get("characteristics"):
                    lines.append(f"- voice_characteristics: {', '.join(voice['characteristics'][:6]) if isinstance(voice['characteristics'], list) else voice['characteristics']}")
                if voice.get("style_notes"):
                    lines.append(f"- style_notes: {voice['style_notes'][:200]}")
            if d.get("confidence"):
                lines.append(f"- dna_confidence: {d['confidence']} (initial DNA — improves as content is added)")

        rendered = "\n".join(lines)
        return rendered[: max_chars - 3] + "..." if len(rendered) > max_chars else rendered


async def load_creator_context(db, user: CurrentUser) -> CreatorContext:
    """Load the creator context for the current caller. Never returns another user's data."""
    # Demo/anonymous → use seeded Alex as demo creator (isolated, DEMO_CREATOR_ID)
    if user.is_demo and not user.is_authenticated:
        import seed_data
        alex = {**seed_data.ALEX, "display_name": seed_data.ALEX["name"]}
        demo_dna = {
            "creator_types": ["youtuber"],
            "topics": [p["name"] for p in alex.get("pillars", [])],
            "content_pillars": [p["name"] for p in alex.get("pillars", [])],
            "audience": {"description": "AI-curious founders and builders",
                          "interests": [a["name"] for a in alex.get("audience_interests", [])]},
            "platforms": ["youtube"],
            "preferred_formats": [f["name"] for f in alex.get("formats", [])[:3]],
            "voice": {"tone": [alex["style"]["tone"]],
                       "style_notes": alex["style"]["hook_style"]},
            "goals": ["grow"], "confidence": "seeded",
            "source": "demo",
        }
        return CreatorContext(alex, demo_dna, None, [], is_demo=True)

    # Real authenticated user
    if not user.creator_id:
        return CreatorContext(None, None, None, [], is_demo=False)

    creator = await CreatorRepo(db).get(user.creator_id)
    dna_snap = await DNARepo(db).latest(user.creator_id)
    intent = await IntentRepo(db).get(user.creator_id)
    platforms = await PlatformRepo(db).list_for_creator(user.creator_id)

    creator_dict = None
    if creator:
        creator_dict = {
            "id": creator.id,
            "display_name": creator.display_name,
            "handle": creator.handle,
            "bio": creator.bio,
            "primary_niche": creator.primary_niche,
            "avatar_url": creator.avatar_url,
            "workspace_id": creator.workspace_id,
        }

    dna_dict = None
    if dna_snap and dna_snap.status.value == "ready":
        # DNA is stored across the structured fields on the snapshot
        dna_dict = {
            "creator_types": (dna_snap.creative_dna or {}).get("creator_types", []),
            "topics": (dna_snap.topic_dna or {}).get("topics", []),
            "subtopics": (dna_snap.topic_dna or {}).get("subtopics", []),
            "content_pillars": (dna_snap.topic_dna or {}).get("content_pillars", []),
            "audience": dna_snap.audience_dna or {},
            "platforms": (dna_snap.creative_dna or {}).get("platforms", []),
            "preferred_formats": (dna_snap.format_dna or {}).get("preferred_formats", []),
            "voice": (dna_snap.creative_dna or {}).get("voice", {}),
            "goals": (dna_snap.creative_dna or {}).get("goals", []),
            "constraints": (dna_snap.creative_dna or {}).get("constraints", []),
            "confidence": (dna_snap.creative_dna or {}).get("confidence", "initial"),
            "source": (dna_snap.creative_dna or {}).get("source", "onboarding"),
            "computed_at": dna_snap.computed_at,
            "version": dna_snap.version,
        }

    platform_dicts = [{"platform": p.platform.value if hasattr(p.platform, "value") else p.platform,
                       "display_name": p.display_name, "handle": p.handle,
                       "status": p.connection_status.value if hasattr(p.connection_status, "value") else p.connection_status,
                       "last_synced_at": p.last_synced_at} for p in platforms]

    intent_dict = intent.model_dump() if intent else None

    return CreatorContext(creator_dict, dna_dict, intent_dict, platform_dicts, is_demo=False)
