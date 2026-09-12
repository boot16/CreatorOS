from typing import Optional

from models.m5 import LearningSignal, CreatorPreferenceEvidence
from models.domain import _now


class LearningSignalRepo:
    def __init__(self, db): self.db = db

    async def add(self, signal: LearningSignal) -> LearningSignal:
        await self.db.learning_signals.insert_one(signal.model_dump())
        return signal

    async def list_for_creator(self, creator_id: str, limit: int = 200) -> list[LearningSignal]:
        cursor = self.db.learning_signals.find(
            {"creator_id": creator_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return [LearningSignal(**doc) async for doc in cursor]


class PreferenceEvidenceRepo:
    def __init__(self, db): self.db = db

    async def get(self, creator_id: str, key: str, scope: str = "global") -> Optional[CreatorPreferenceEvidence]:
        doc = await self.db.creator_preference_evidence.find_one(
            {"creator_id": creator_id, "key": key, "scope": scope}, {"_id": 0}
        )
        return CreatorPreferenceEvidence(**doc) if doc else None

    async def upsert(self, item: CreatorPreferenceEvidence) -> CreatorPreferenceEvidence:
        item.updated_at = _now()
        await self.db.creator_preference_evidence.update_one(
            {"creator_id": item.creator_id, "key": item.key, "scope": item.scope},
            {"$set": item.model_dump()}, upsert=True,
        )
        return item

    async def list_active(self, creator_id: str, limit: int = 30) -> list[CreatorPreferenceEvidence]:
        cursor = self.db.creator_preference_evidence.find(
            {"creator_id": creator_id, "status": {"$in": ["hypothesis", "active"]}}, {"_id": 0}
        ).sort([("confidence", -1), ("updated_at", -1)]).limit(limit)
        return [CreatorPreferenceEvidence(**doc) async for doc in cursor]
