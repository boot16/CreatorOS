"""Persistence for M5 creative directions and readiness assessments."""
from datetime import datetime, timezone
from typing import Optional

from models.m5 import CreativeDirectionV2, DirectionReadiness


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreativeDirectionRepo:
    def __init__(self, db):
        self.db = db

    async def list_for_project(self, project_id: str, creator_id: str) -> list[CreativeDirectionV2]:
        cursor = self.db.creative_directions.find(
            {"project_id": project_id, "creator_id": creator_id}, {"_id": 0}
        ).sort("created_at", 1)
        return [CreativeDirectionV2(**doc) async for doc in cursor]

    async def get(self, direction_id: str, project_id: str, creator_id: str) -> Optional[CreativeDirectionV2]:
        doc = await self.db.creative_directions.find_one(
            {"id": direction_id, "project_id": project_id, "creator_id": creator_id}, {"_id": 0}
        )
        return CreativeDirectionV2(**doc) if doc else None

    async def get_selected(self, project_id: str, creator_id: str) -> Optional[CreativeDirectionV2]:
        doc = await self.db.creative_directions.find_one(
            {"project_id": project_id, "creator_id": creator_id, "status": "selected"}, {"_id": 0},
            sort=[("updated_at", -1)],
        )
        return CreativeDirectionV2(**doc) if doc else None

    async def insert(self, item: CreativeDirectionV2) -> CreativeDirectionV2:
        await self.db.creative_directions.insert_one(item.model_dump())
        return item

    async def insert_many(self, items: list[CreativeDirectionV2]) -> list[CreativeDirectionV2]:
        if items:
            await self.db.creative_directions.insert_many([item.model_dump() for item in items])
        return items

    async def mark_selected(self, direction_id: str, project_id: str, creator_id: str) -> Optional[CreativeDirectionV2]:
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

    async def mark_rejected(self, direction_id: str, project_id: str, creator_id: str) -> Optional[CreativeDirectionV2]:
        result = await self.db.creative_directions.update_one(
            {"id": direction_id, "project_id": project_id, "creator_id": creator_id},
            {"$set": {"status": "rejected", "updated_at": _now()}},
        )
        if result.matched_count == 0:
            return None
        return await self.get(direction_id, project_id, creator_id)


class DirectionReadinessRepo:
    def __init__(self, db):
        self.db = db

    async def get_current(
        self,
        project_id: str,
        creator_id: str,
        direction_id: str,
        direction_revision: int,
    ) -> Optional[DirectionReadiness]:
        doc = await self.db.direction_readiness.find_one(
            {
                "project_id": project_id,
                "creator_id": creator_id,
                "direction_id": direction_id,
                "direction_revision": direction_revision,
            },
            {"_id": 0},
        )
        return DirectionReadiness(**doc) if doc else None

    async def upsert(self, item: DirectionReadiness) -> DirectionReadiness:
        item.updated_at = _now()
        await self.db.direction_readiness.update_one(
            {
                "project_id": item.project_id,
                "creator_id": item.creator_id,
                "direction_id": item.direction_id,
                "direction_revision": item.direction_revision,
            },
            {"$set": item.model_dump()},
            upsert=True,
        )
        return item
