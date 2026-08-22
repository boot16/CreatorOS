"""Provider layer — resolves data source based on DATA_MODE.

Demo provider returns fixtures (Alex/Sarah/trends).
Production provider returns real persisted entities or explicit not_computed status.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Any
from datetime import datetime, timezone

from core.config import get_settings
from core.identity import CurrentUser, DEMO_CREATOR_ID
from repositories import CreatorRepo, YouTubeSourceRepo, DNARepo, IntentRepo
import seed_data


class CreatorProvider(ABC):
    @abstractmethod
    async def get_creator(self, creator_id: str, requester: CurrentUser) -> Optional[dict]: ...
    @abstractmethod
    async def get_current_creator(self, requester: CurrentUser) -> Optional[dict]: ...


class TrendProvider(ABC):
    @abstractmethod
    async def list_trends(self, category: Optional[str] = None) -> Any: ...
    @abstractmethod
    async def get_trend(self, trend_id: str) -> Optional[dict]: ...


class OpportunityProvider(ABC):
    @abstractmethod
    async def list_for_creator(self, requester: CurrentUser) -> dict: ...
    @abstractmethod
    async def get(self, opp_id: str, requester: CurrentUser) -> Optional[dict]: ...


# ---------- DEMO providers ----------
class DemoCreatorProvider(CreatorProvider):
    async def get_creator(self, creator_id: str, requester: CurrentUser) -> Optional[dict]:
        if creator_id in (DEMO_CREATOR_ID, "alex-morgan"):
            return {**seed_data.ALEX, "historical_videos": seed_data.HISTORICAL_VIDEOS}
        if creator_id == "sarah-chen":
            return seed_data.SARAH
        return None
    async def get_current_creator(self, requester: CurrentUser) -> Optional[dict]:
        return await self.get_creator(DEMO_CREATOR_ID, requester)


class DemoTrendProvider(TrendProvider):
    async def list_trends(self, category=None):
        if category and category.lower() != "all":
            return [t for t in seed_data.TRENDS if t["category"].lower() == category.lower()]
        return seed_data.TRENDS
    async def get_trend(self, trend_id):
        return next((t for t in seed_data.TRENDS if t["id"] == trend_id), None)


class DemoOpportunityProvider(OpportunityProvider):
    async def list_for_creator(self, requester: CurrentUser) -> dict:
        items = [o for o in seed_data.OPPORTUNITIES if o["creator_id"] == "alex-morgan"]
        return {
            "status": "ready",
            "items": [
                {**o,
                 "score": seed_data.compute_opportunity_score(o["sub_scores"]),
                 "trend": next((t for t in seed_data.TRENDS if t["id"] == o["trend_id"]), None)}
                for o in items
            ],
        }
    async def get(self, opp_id, requester):
        o = next((x for x in seed_data.OPPORTUNITIES if x["id"] == opp_id), None)
        if not o:
            return None
        return {**o,
                "score": seed_data.compute_opportunity_score(o["sub_scores"]),
                "trend": next((t for t in seed_data.TRENDS if t["id"] == o["trend_id"]), None),
                "creator": await DemoCreatorProvider().get_creator(o["creator_id"], requester)}


# ---------- PRODUCTION providers ----------
class ProductionCreatorProvider(CreatorProvider):
    def __init__(self, creator_repo: CreatorRepo, videos_repo: YouTubeSourceRepo):
        self.creator_repo = creator_repo
        self.videos_repo = videos_repo

    async def get_creator(self, creator_id: str, requester: CurrentUser) -> Optional[dict]:
        c = await self.creator_repo.get(creator_id)
        if not c:
            return None
        # ownership check
        if requester.workspace_id and c.workspace_id != requester.workspace_id:
            return None
        vids = await self.videos_repo.list_videos(c.id, limit=20)
        return {
            "id": c.id,
            "name": c.display_name,
            "handle": c.handle,
            "niche": c.primary_niche,
            "bio": c.bio,
            "avatar_url": c.avatar_url,
            "historical_videos": [
                {"title": v.title, "views": 0, "format": "Video",
                 "grad": ["#8A2BE2", "#4C1D95"], "thumbnail_url": v.thumbnail_url}
                for v in vids
            ],
        }

    async def get_current_creator(self, requester: CurrentUser) -> Optional[dict]:
        if not requester.creator_id:
            return None
        return await self.get_creator(requester.creator_id, requester)


class ProductionTrendProvider(TrendProvider):
    """No real trend pipeline yet — honest not_computed."""
    async def list_trends(self, category=None):
        return {"status": "not_computed", "items": []}
    async def get_trend(self, trend_id):
        return None


class ProductionOpportunityProvider(OpportunityProvider):
    """No candidate generation yet — honest empty."""
    async def list_for_creator(self, requester: CurrentUser) -> dict:
        return {"status": "not_computed", "items": []}
    async def get(self, opp_id, requester):
        return None


# ---------- Factory ----------
def make_creator_provider(db) -> CreatorProvider:
    if get_settings().is_demo:
        return DemoCreatorProvider()
    return ProductionCreatorProvider(CreatorRepo(db), YouTubeSourceRepo(db))


def make_trend_provider() -> TrendProvider:
    return DemoTrendProvider() if get_settings().is_demo else ProductionTrendProvider()


def make_opportunity_provider() -> OpportunityProvider:
    return DemoOpportunityProvider() if get_settings().is_demo else ProductionOpportunityProvider()
