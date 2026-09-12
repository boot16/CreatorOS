from typing import Optional

from models.m5 import ProjectFoundation
from models.domain import _now


class ProjectFoundationRepo:
    def __init__(self, db):
        self.db = db

    async def get(self, project_id: str, creator_id: str) -> Optional[ProjectFoundation]:
        doc = await self.db.project_foundations.find_one(
            {"project_id": project_id, "creator_id": creator_id}, {"_id": 0}
        )
        return ProjectFoundation(**doc) if doc else None

    async def upsert(self, item: ProjectFoundation) -> ProjectFoundation:
        existing = await self.get(item.project_id, item.creator_id)
        if existing:
            item.id = existing.id
            item.created_at = existing.created_at
            item.version = existing.version + 1
        item.updated_at = _now()
        await self.db.project_foundations.update_one(
            {"project_id": item.project_id, "creator_id": item.creator_id},
            {"$set": item.model_dump()}, upsert=True,
        )
        return item

    async def patch(self, project_id: str, creator_id: str, patch: dict) -> Optional[ProjectFoundation]:
        current = await self.get(project_id, creator_id)
        if not current:
            return None
        data = current.model_dump()
        data.update(patch)
        data["version"] = current.version + 1
        data["updated_at"] = _now()
        item = ProjectFoundation(**data)
        await self.db.project_foundations.replace_one(
            {"project_id": project_id, "creator_id": creator_id}, item.model_dump()
        )
        return item
