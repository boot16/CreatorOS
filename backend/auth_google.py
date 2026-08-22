"""Google OAuth + YouTube channel ingest.

Env vars required (set in /app/backend/.env, restart backend):
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- OAUTH_REDIRECT_URI    (must match one registered in Google Cloud Console)
- FRONTEND_URL          (used for final redirect after login)
- SESSION_SECRET        (any long random string)

Setup steps (shown to user in the app when unset):
1. Go to https://console.cloud.google.com/apis/credentials
2. Create OAuth 2.0 Client ID (type: Web application)
3. Add authorized redirect URI: <OAUTH_REDIRECT_URI value>
4. Enable "YouTube Data API v3" at https://console.cloud.google.com/apis/library/youtube.googleapis.com
5. Copy Client ID + Secret into backend/.env, then restart backend

Scopes requested:
- openid + email + profile   (identity)
- https://www.googleapis.com/auth/youtube.readonly  (channel + video read)
"""
import os
import uuid
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException, Response, Cookie
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

AUTH_SCOPES = "openid email profile https://www.googleapis.com/auth/youtube.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YT_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

SESSION_COOKIE = "creatoros_sid"


def config():
    return {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.environ.get("OAUTH_REDIRECT_URI", "").strip(),
        "frontend_url": os.environ.get("FRONTEND_URL", "").strip(),
    }


def is_configured() -> bool:
    c = config()
    return bool(c["client_id"] and c["client_secret"] and c["redirect_uri"])


def build_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.get("/status")
    async def status(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        c = config()
        configured = is_configured()
        setup_guide = None if configured else {
            "steps": [
                "Go to https://console.cloud.google.com/apis/credentials",
                "Create OAuth 2.0 Client ID (type: Web application)",
                f"Add this authorized redirect URI: {c['redirect_uri'] or '(set OAUTH_REDIRECT_URI in .env)'}",
                "Enable YouTube Data API v3: https://console.cloud.google.com/apis/library/youtube.googleapis.com",
                "Paste Client ID + Secret into /app/backend/.env → restart backend",
            ],
            "redirect_uri": c["redirect_uri"],
        }
        user = None
        if sid:
            sess = await db.sessions.find_one({"sid": sid}, {"_id": 0})
            if sess:
                user = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0, "refresh_token": 0, "access_token": 0})
        return {"configured": configured, "setup_guide": setup_guide, "user": user}

    @router.get("/google/login")
    async def google_login():
        if not is_configured():
            raise HTTPException(400, "Google OAuth not configured — check /api/auth/status for setup steps.")
        c = config()
        state = secrets.token_urlsafe(24)
        await db.oauth_states.insert_one({"state": state, "created_at": datetime.now(timezone.utc).isoformat()})
        params = {
            "client_id": c["client_id"],
            "redirect_uri": c["redirect_uri"],
            "response_type": "code",
            "scope": AUTH_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "include_granted_scopes": "true",
        }
        url = AUTH_URL + "?" + "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        return RedirectResponse(url)

    @router.get("/google/callback")
    async def google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
        c = config()
        fe = c["frontend_url"] or "/"
        if error:
            return RedirectResponse(f"{fe}/?auth_error={error}")
        if not code or not state:
            return RedirectResponse(f"{fe}/?auth_error=missing_code")
        st = await db.oauth_states.find_one({"state": state})
        if not st:
            return RedirectResponse(f"{fe}/?auth_error=bad_state")
        await db.oauth_states.delete_one({"state": state})

        # Exchange code for tokens
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(TOKEN_URL, data={
                "code": code,
                "client_id": c["client_id"],
                "client_secret": c["client_secret"],
                "redirect_uri": c["redirect_uri"],
                "grant_type": "authorization_code",
            })
            if token_resp.status_code != 200:
                return RedirectResponse(f"{fe}/?auth_error=token_exchange_failed")
            tokens = token_resp.json()
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")

            # Get identity
            uinfo = (await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})).json()

            # Get YouTube channel (own)
            ch_resp = await client.get(YT_CHANNELS_URL, params={
                "part": "snippet,statistics,contentDetails",
                "mine": "true",
            }, headers={"Authorization": f"Bearer {access_token}"})
            channel = None
            recent_videos = []
            if ch_resp.status_code == 200 and ch_resp.json().get("items"):
                channel = ch_resp.json()["items"][0]
                uploads_pl = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                if uploads_pl:
                    pl = await client.get(YT_PLAYLIST_ITEMS_URL, params={
                        "part": "snippet,contentDetails",
                        "playlistId": uploads_pl,
                        "maxResults": 20,
                    }, headers={"Authorization": f"Bearer {access_token}"})
                    video_ids = [it["contentDetails"]["videoId"] for it in pl.json().get("items", [])]
                    if video_ids:
                        vids = await client.get(YT_VIDEOS_URL, params={
                            "part": "snippet,statistics",
                            "id": ",".join(video_ids),
                        }, headers={"Authorization": f"Bearer {access_token}"})
                        for v in vids.json().get("items", []):
                            recent_videos.append({
                                "id": v["id"],
                                "title": v["snippet"]["title"],
                                "thumbnail": v["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
                                "views": int(v["statistics"].get("viewCount", 0)),
                                "published_at": v["snippet"]["publishedAt"],
                            })

        # Persist user
        user_id = uinfo.get("sub") or str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": uinfo.get("email"),
            "name": uinfo.get("name"),
            "picture": uinfo.get("picture"),
            "youtube_channel": {
                "id": channel["id"] if channel else None,
                "title": channel["snippet"]["title"] if channel else None,
                "description": channel["snippet"].get("description", "") if channel else "",
                "thumbnail": (channel["snippet"].get("thumbnails", {}).get("default", {}) or {}).get("url", "") if channel else None,
                "subscribers": int(channel["statistics"].get("subscriberCount", 0)) if channel else 0,
                "video_count": int(channel["statistics"].get("videoCount", 0)) if channel else 0,
                "view_count": int(channel["statistics"].get("viewCount", 0)) if channel else 0,
            } if channel else None,
            "recent_videos": recent_videos,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.update_one({"id": user_id}, {"$set": user_doc}, upsert=True)

        # Create session
        sid = secrets.token_urlsafe(32)
        await db.sessions.insert_one({
            "sid": sid,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        resp = RedirectResponse(f"{fe}/app/dna?connected=1")
        resp.set_cookie(SESSION_COOKIE, sid, max_age=60 * 60 * 24 * 30, httponly=True, samesite="lax", secure=True, path="/")
        return resp

    @router.post("/logout")
    async def logout(response: Response, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        if sid:
            await db.sessions.delete_one({"sid": sid})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    return router


async def current_user(db, sid: Optional[str]):
    if not sid:
        return None
    sess = await db.sessions.find_one({"sid": sid}, {"_id": 0})
    if not sess:
        return None
    return await db.users.find_one({"id": sess["user_id"]}, {"_id": 0, "access_token": 0, "refresh_token": 0})
