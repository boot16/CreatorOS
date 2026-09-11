"""Persistence for M5 idea-understanding state.

One canonical understanding document exists per project. The repository always scopes
reads/writes by creator_id as a second ownership boundary in addition to project checks.
"""
from datetime import datetime, timezone
from typing import Optional

from models.domain import IdeaUnderstanding


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdeaUnderstandingRepo:
    def __init__(self, db):
        self.db = db

    async def get(self, project_id: str, creator_id: str) -> Optional[IdeaUnderstanding]:
        doc = await self.db.idea_understandings.find_one(
            {"project_id": project_id, "creator_id": creator_id}, {"_id": 0}
        )
        return IdeaUnderstanding(**doc) if doc else None

    async def upsert(self, understanding: IdeaUnderstanding) -> IdeaUnderstanding:
        existing = await self.get(understanding.project_id, understanding.creator_id)
        if existing:
            understanding.id = existing.id
            understanding.created_at = existing.created_at
            understanding.version = existing.version + 1
        understanding.updated_at = _now()
        await self.db.idea_understandings.update_one(
            {"project_id": understanding.project_id, "creator_id": understanding.creator_id},
            {"$set": understanding.model_dump()},
            upsert=True,
        )
        return understanding

    async def patch_confirmed_fields(
        self,
        project_id: str,
        creator_id: str,
        field_values: dict,
        *,
        assumptions: Optional[list[str]] = None,
        open_questions: Optional[list[str]] = None,
        material_unknowns: Optional[list[str]] = None,
    ) -> Optional[IdeaUnderstanding]:
        current = await self.get(project_id, creator_id)
        if not current:
            return None

        for name, value in field_values.items():
            field = getattr(current, name, None)
            if field is None:
                continue
            field.value = value.strip() if isinstance(value, str) else value
            field.origin = "confirmed"
            field.confidence = 1.0

        if assumptions is not None:
            current.assumptions = assumptions
        if open_questions is not None:
            current.open_questions = open_questions
        if material_unknowns is not None:
            current.material_unknowns = material_unknowns

        current.version += 1
        current.updated_at = _now()
        await self.db.idea_understandings.update_one(
            {"project_id": project_id, "creator_id": creator_id},
            {"$set": current.model_dump()},
        )
        return current
