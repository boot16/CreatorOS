"""Repositories for per-video content analysis."""
from typing import Optional, List
from models.dna import VideoContentAnalysis


class VideoAnalysisRepo:
    def __init__(self, db): self.db = db
    async def find_reusable(self, *, creator_video_id: str, source_content_hash: str,
                             prompt_version: str, pipeline_version: str, model: str) -> Optional[VideoContentAnalysis]:
        doc = await self.db.video_content_analysis.find_one({
            "creator_video_id": creator_video_id,
            "source_content_hash": source_content_hash,
            "prompt_version": prompt_version,
            "pipeline_version": pipeline_version,
            "model": model,
            "status": "success",
        }, {"_id": 0})
        return VideoContentAnalysis(**doc) if doc else None
    async def upsert(self, an: VideoContentAnalysis):
        await self.db.video_content_analysis.update_one(
            {"creator_video_id": an.creator_video_id, "source_content_hash": an.source_content_hash,
             "prompt_version": an.prompt_version, "pipeline_version": an.pipeline_version, "model": an.model},
            {"$set": an.model_dump()}, upsert=True,
        )
    async def list_for_creator(self, creator_id: str) -> List[VideoContentAnalysis]:
        cursor = self.db.video_content_analysis.find(
            {"creator_id": creator_id, "status": "success"}, {"_id": 0}
        )
        return [VideoContentAnalysis(**d) async for d in cursor]
