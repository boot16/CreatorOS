"""Idempotent YouTube data sync service.

Responsibilities:
  1. Resolve connected YouTube platform for the creator
  2. Fetch channel + recent videos from YouTube Data API v3 using stored credential
  3. Store channel snapshot, upsert canonical videos, add metric snapshots
  4. Update last_synced_at

Never mutates ownership — always requires creator_id owned by caller.
"""
from datetime import datetime, timezone
from typing import Optional
import httpx

from core.encryption import decrypt
from core.errors import AppError, Codes
from core.logging import get_logger
from models.domain import (
    ConnectedPlatform, YouTubeChannelSnapshot, CreatorVideo, VideoMetricSnapshot,
)
from repositories import PlatformRepo, CredentialRepo, YouTubeSourceRepo

log = get_logger("services.youtube_sync")

YT_CHANNELS = "https://www.googleapis.com/youtube/v3/channels"
YT_PLAYLIST = "https://www.googleapis.com/youtube/v3/playlistItems"
YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeSyncService:
    def __init__(self, db, http_client: Optional[httpx.AsyncClient] = None):
        self.platform_repo = PlatformRepo(db)
        self.cred_repo = CredentialRepo(db)
        self.source_repo = YouTubeSourceRepo(db)
        self.http = http_client  # if None, one is created per sync

    async def sync(self, creator_id: str) -> dict:
        cp = await self.platform_repo.get_for_creator(creator_id, "youtube")
        if not cp:
            raise AppError(Codes.YOUTUBE_NOT_CONNECTED,
                           "Connect a YouTube channel before syncing creator data.", status_code=400)
        cred = await self.cred_repo.get(cp.id)
        if not cred or not cred.encrypted_access_token:
            raise AppError(Codes.YOUTUBE_NOT_CONNECTED, "Missing YouTube credentials — reconnect required.", status_code=400)

        access_token = decrypt(cred.encrypted_access_token)
        headers = {"Authorization": f"Bearer {access_token}"}

        owns_client = self.http is None
        client = self.http or httpx.AsyncClient(timeout=15)
        try:
            channel = await self._fetch_channel(client, headers)
            if not channel:
                raise AppError(Codes.UPSTREAM_ERROR, "YouTube returned no channel data.", status_code=502)

            snap = YouTubeChannelSnapshot(
                creator_id=creator_id,
                connected_platform_id=cp.id,
                channel_id=channel["id"],
                title=channel["snippet"]["title"],
                description=channel["snippet"].get("description", "")[:1000],
                subscriber_count=int(channel["statistics"].get("subscriberCount", 0)),
                view_count=int(channel["statistics"].get("viewCount", 0)),
                video_count=int(channel["statistics"].get("videoCount", 0)),
            )
            await self.source_repo.add_channel_snapshot(snap)

            uploads_pl = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
            created, updated, videos_seen = 0, 0, 0
            if uploads_pl:
                pl_items = await self._fetch_playlist_items(client, headers, uploads_pl)
                video_ids = [i["contentDetails"]["videoId"] for i in pl_items][:20]
                videos_seen = len(video_ids)
                if video_ids:
                    vids = await self._fetch_videos(client, headers, video_ids)
                    for v in vids:
                        cv = CreatorVideo(
                            creator_id=creator_id,
                            connected_platform_id=cp.id,
                            external_video_id=v["id"],
                            title=v["snippet"]["title"],
                            description=v["snippet"].get("description", "")[:500],
                            thumbnail_url=v["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                            published_at=v["snippet"]["publishedAt"],
                        )
                        _, was_created = await self.source_repo.upsert_video(cv)
                        if was_created: created += 1
                        else: updated += 1
                        metric = VideoMetricSnapshot(
                            creator_video_id=cv.id,
                            views=int(v["statistics"].get("viewCount", 0)),
                            likes=int(v["statistics"].get("likeCount", 0)),
                            comments=int(v["statistics"].get("commentCount", 0)),
                        )
                        await self.source_repo.add_metric_snapshot(metric)

            await self.platform_repo.mark_synced(cp.id)
            log.info(f"youtube_sync creator_id={creator_id} videos_seen={videos_seen} created={created} updated={updated}")
            return {
                "creator_id": creator_id,
                "videos_seen": videos_seen,
                "videos_created": created,
                "videos_updated": updated,
                "snapshot_time": snap.captured_at,
                "status": "success",
            }
        finally:
            if owns_client:
                await client.aclose()

    async def _fetch_channel(self, client, headers):
        r = await client.get(YT_CHANNELS, params={"part": "snippet,statistics,contentDetails", "mine": "true"}, headers=headers)
        if r.status_code != 200:
            raise AppError(Codes.UPSTREAM_ERROR, f"YouTube channels error {r.status_code}", status_code=502)
        items = r.json().get("items", [])
        return items[0] if items else None

    async def _fetch_playlist_items(self, client, headers, playlist_id):
        r = await client.get(YT_PLAYLIST, params={"part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": 20}, headers=headers)
        return r.json().get("items", []) if r.status_code == 200 else []

    async def _fetch_videos(self, client, headers, video_ids):
        r = await client.get(YT_VIDEOS, params={"part": "snippet,statistics", "id": ",".join(video_ids)}, headers=headers)
        return r.json().get("items", []) if r.status_code == 200 else []
