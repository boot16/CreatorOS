"""Persistence for M5 creative directions."""
from datetime import datetime, timezone
from typing import Optional

from models.domain import CreativeDirection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreativeDirectionRepo:
    def __init__(self, db):
        self.db = db

    async def list_for_project(self, project_id: str, creator_id: str) -> list[CreativeDirection]:
        cursor = self.db.creative_directions.find(
            {"project_id": project_id, "creator_id": creator_id}, {"_id": 0}
        ).sort("created_at", 1)
        return [CreativeDirection(**doc) async for doc in cursor]

    async def get(self, direction_id: str, project_id: str, creator_id: str) -> Optional[CreativeDirection]:
        doc = await self.db.creative_directions.find_one(
            {"id": direction_id, "project_id": project_id, "creator_id": creator_id}, {"_id": 0}
        )
        return CreativeDirection(**doc) if doc else None

    async def insert_many(self, items: list[CreativeDirection]) -> list[CreativeDirection]:
        if items:
            await self.db.creative_directions.insert_many([item.model_dump() for item in items])
        return items

    async def mark_selected(self, direction_id: str, project_id: str, creator_id: str) -> Optional[CreativeDirection]:
        now = _now()
        await self.db.creative_directions.update_many(
            {"project_id": project_id, "creator_id": creator_id, "status": "selected"},
            {"$set": {"status": "proposed", "updated_at": now}},
        )
        result = await self.db.creative_directions.update_one(
            {"id": direction_id, "project_id": project_id, "creator_id": creator_id},
            {"$set": {"status": "selected", "updated_at": now}},
        )
        if result.matched_count == 0:
            return None
        return await self.get(direction_id, project_id, creator_id)

    async def mark_rejected(self, direction_id: str, project_id: str, creator_id: str) -> Optional[CreativeDirection]:
        result = await self.db.creative_directions.update_one(
            {"id": direction_id, "project_id": project_id, "creator_id": creator_id},
            {"$set": {"status": "rejected", "updated_at": _now()}},
        )
        if result.matched_count == 0:
            return None
        return await self.get(direction_id, project_id, creator_id)
