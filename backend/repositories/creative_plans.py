"""Persistence for versioned M5 creative plans."""
from datetime import datetime, timezone
from typing import Optional

from models.m5 import ReelCreativePlan


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreativePlanRepo:
    def __init__(self, db):
        self.db = db

    async def latest_for_direction(
        self,
        project_id: str,
        creator_id: str,
        direction_id: str,
        direction_revision: int,
    ) -> Optional[ReelCreativePlan]:
        doc = await self.db.creative_plans.find_one(
            {
                "project_id": project_id,
                "creator_id": creator_id,
                "direction_id": direction_id,
                "direction_revision": direction_revision,
            },
            {"_id": 0},
            sort=[("version", -1)],
        )
        return ReelCreativePlan(**doc) if doc else None

    async def create_next(self, item: ReelCreativePlan) -> ReelCreativePlan:
        previous = await self.latest_for_direction(
            item.project_id,
            item.creator_id,
            item.direction_id,
            item.direction_revision,
        )
        item.version = (previous.version + 1) if previous else 1
        item.updated_at = _now()
        await self.db.creative_plans.insert_one(item.model_dump())
        return item

    async def get(self, plan_id: str, project_id: str, creator_id: str) -> Optional[ReelCreativePlan]:
        doc = await self.db.creative_plans.find_one(
            {"id": plan_id, "project_id": project_id, "creator_id": creator_id},
            {"_id": 0},
        )
        return ReelCreativePlan(**doc) if doc else None

    async def update_status(self, plan_id: str, project_id: str, creator_id: str, status: str) -> Optional[ReelCreativePlan]:
        result = await self.db.creative_plans.update_one(
            {"id": plan_id, "project_id": project_id, "creator_id": creator_id},
            {"$set": {"status": status, "updated_at": _now()}},
        )
        if result.matched_count == 0:
            return None
        return await self.get(plan_id, project_id, creator_id)
