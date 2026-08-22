"""Google OAuth + YouTube connect.

Refactored for Phase 1 production foundation:
- Access + refresh tokens are stored ENCRYPTED in `platform_credentials` (not in `users`)
- Session has server-side expires_at
- On login: ensure User → Workspace → Creator → ConnectedPlatform pipeline
- Never returns tokens to the client
"""
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Cookie
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import get_settings
from core.encryption import encrypt
from core.identity import SESSION_COOKIE
from core.logging import get_logger
from models.domain import PlatformCredential
from repositories import UserRepo, WorkspaceRepo, CreatorRepo, PlatformRepo, CredentialRepo, SessionRepo

log = get_logger("auth.google")

AUTH_SCOPES = "openid email profile https://www.googleapis.com/auth/youtube.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def is_configured() -> bool:
    s = get_settings()
    return bool(s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET and s.OAUTH_REDIRECT_URI)


def build_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])
    session_repo = SessionRepo(db, max_age_seconds=get_settings().SESSION_MAX_AGE)

    @router.get("/status")
    async def status(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        s = get_settings()
        configured = is_configured()
        setup_guide = None if configured else {
            "steps": [
                "Go to https://console.cloud.google.com/apis/credentials",
                "Create OAuth 2.0 Client ID (type: Web application)",
                f"Add this authorized redirect URI: {s.OAUTH_REDIRECT_URI or '(set OAUTH_REDIRECT_URI in .env)'}",
                "Enable YouTube Data API v3: https://console.cloud.google.com/apis/library/youtube.googleapis.com",
                "Paste Client ID + Secret into /app/backend/.env → restart backend",
            ],
            "redirect_uri": s.OAUTH_REDIRECT_URI,
        }
        user = None
        if sid:
            sess = await db.sessions.find_one({"sid": sid}, {"_id": 0})
            if sess and datetime.fromisoformat(sess["expires_at"]) >= datetime.now(timezone.utc):
                u = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0})
                if u:
                    user = {"id": u["id"], "name": u.get("name"), "email": u.get("email"), "picture": u.get("picture")}
        return {"configured": configured, "setup_guide": setup_guide, "user": user}

    @router.get("/google/login")
    async def google_login():
        from core.errors import AppError, Codes
        if not is_configured():
            raise AppError(Codes.NOT_CONFIGURED, "Google OAuth not configured — check /api/auth/status for setup steps.", status_code=400)
        s = get_settings()
        state = secrets.token_urlsafe(24)
        await db.oauth_states.insert_one({
            "state": state,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_at_ts": datetime.now(timezone.utc),  # for TTL index
        })
        params = {
            "client_id": s.GOOGLE_CLIENT_ID,
            "redirect_uri": s.OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": AUTH_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        url = AUTH_URL + "?" + "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        return RedirectResponse(url)

    @router.get("/google/callback")
    async def google_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
        s = get_settings()
        fe = s.FRONTEND_URL or "/"
        if error or not code or not state:
            return RedirectResponse(f"{fe}/?auth_error={error or 'missing_code'}")
        st = await db.oauth_states.find_one({"state": state})
        if not st:
            return RedirectResponse(f"{fe}/?auth_error=bad_state")
        await db.oauth_states.delete_one({"state": state})

        async with httpx.AsyncClient(timeout=15) as client:
            tk = await client.post(TOKEN_URL, data={
                "code": code, "client_id": s.GOOGLE_CLIENT_ID, "client_secret": s.GOOGLE_CLIENT_SECRET,
                "redirect_uri": s.OAUTH_REDIRECT_URI, "grant_type": "authorization_code",
            })
            if tk.status_code != 200:
                log.warning(f"token_exchange_failed status={tk.status_code}")
                return RedirectResponse(f"{fe}/?auth_error=token_exchange_failed")
            tokens = tk.json()
            access_token = tokens["access_token"]
            refresh_token = tokens.get("refresh_token")

            uinfo = (await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})).json()

            channel = None
            ch_resp = await client.get(YT_CHANNELS_URL, params={"part": "snippet,statistics,contentDetails", "mine": "true"},
                                        headers={"Authorization": f"Bearer {access_token}"})
            if ch_resp.status_code == 200 and ch_resp.json().get("items"):
                channel = ch_resp.json()["items"][0]

        # Ensure User → Workspace → Creator → ConnectedPlatform
        user_repo = UserRepo(db); ws_repo = WorkspaceRepo(db)
        creator_repo = CreatorRepo(db); platform_repo = PlatformRepo(db)
        cred_repo = CredentialRepo(db)

        google_sub = uinfo.get("sub")
        user = await user_repo.upsert_by_google_sub(google_sub, {
            "email": uinfo.get("email"), "name": uinfo.get("name"), "picture": uinfo.get("picture"),
        })
        ws_name = channel["snippet"]["title"] if channel else (user.name or "Workspace")
        workspace = await ws_repo.create_owner_workspace(user.id, ws_name)
        creator = await creator_repo.upsert_for_user(user.id, workspace.id, {
            "display_name": (channel["snippet"]["title"] if channel else user.name) or "Creator",
            "handle": channel["snippet"]["title"] if channel else None,
            "bio": (channel["snippet"].get("description", "")[:500] if channel else ""),
            "avatar_url": ((channel["snippet"].get("thumbnails", {}).get("default", {}) or {}).get("url") if channel else user.picture),
        })

        if channel:
            cp = await platform_repo.upsert(
                creator.id, "youtube", google_sub, {
                    "external_channel_id": channel["id"],
                    "display_name": channel["snippet"]["title"],
                    "handle": channel["snippet"]["title"],
                    "metadata": {
                        "subscribers": int(channel["statistics"].get("subscriberCount", 0)),
                        "video_count": int(channel["statistics"].get("videoCount", 0)),
                    },
                    "connection_status": "connected",
                    "connected_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            # Encrypt tokens before persistence
            cred = PlatformCredential(
                connected_platform_id=cp.id,
                encrypted_access_token=encrypt(access_token),
                encrypted_refresh_token=encrypt(refresh_token) if refresh_token else None,
                scopes=AUTH_SCOPES.split(),
            )
            await cred_repo.upsert(cp.id, cred)

        # Session
        sid = secrets.token_urlsafe(32)
        await session_repo.create(sid, user.id, user.email, user.name)

        resp = RedirectResponse(f"{fe}/app/dna?connected=1")
        resp.set_cookie(SESSION_COOKIE, sid, max_age=get_settings().SESSION_MAX_AGE,
                         httponly=True, samesite="lax", secure=True, path="/")
        return resp

    @router.post("/logout")
    async def logout(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        if sid:
            await session_repo.revoke(sid)
        from fastapi.responses import JSONResponse
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(SESSION_COOKIE, path="/")
        return resp

    return router


# Legacy helper kept for backward compat with features.py — resolves user by session id.
async def current_user(db, sid: Optional[str]):
    if not sid:
        return None
    sess = await db.sessions.find_one({"sid": sid}, {"_id": 0})
    if not sess:
        return None
    exp = sess.get("expires_at")
    if exp and datetime.fromisoformat(exp) < datetime.now(timezone.utc):
        return None
    u = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0})
    if not u:
        return None
    return {"id": u["id"], "email": u.get("email"), "name": u.get("name"), "picture": u.get("picture")}
