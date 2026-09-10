"""Google identity login + optional YouTube connection.

Production foundation:
- Google login uses identity-only scopes.
- YouTube connection is a separate authenticated OAuth flow.
- Access/refresh tokens are stored encrypted in platform_credentials.
- Session is server-side and cookie settings work on localhost + production.
- OAuth state records are single-use and explicitly age-checked.
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import get_settings
from core.encryption import encrypt
from core.identity import SESSION_COOKIE
from core.logging import get_logger
from models.domain import PlatformCredential
from repositories import UserRepo, WorkspaceRepo, CreatorRepo, PlatformRepo, CredentialRepo, SessionRepo

log = get_logger("auth.google")

IDENTITY_SCOPES = "openid email profile"
YOUTUBE_SCOPES = "openid email profile https://www.googleapis.com/auth/youtube.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
STATE_TTL_MINUTES = 10


def is_configured() -> bool:
    s = get_settings()
    return bool(s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET and s.OAUTH_REDIRECT_URI)


def _oauth_url(scopes: str, state: str, *, force_consent: bool = False) -> str:
    s = get_settings()
    params = {
        "client_id": s.GOOGLE_CLIENT_ID,
        "redirect_uri": s.OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "include_granted_scopes": "true",
    }
    if force_consent:
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    qp = httpx.QueryParams(params)
    return f"{AUTH_URL}?{qp}"


async def _get_valid_session(db, sid: Optional[str]) -> Optional[dict]:
    if not sid:
        return None
    sess = await db.sessions.find_one({"sid": sid}, {"_id": 0})
    if not sess:
        return None
    exp = sess.get("expires_at")
    if exp and datetime.fromisoformat(exp) < datetime.now(timezone.utc):
        await db.sessions.delete_one({"sid": sid})
        return None
    return sess


def _set_session_cookie(resp, sid: str):
    s = get_settings()
    resp.set_cookie(
        SESSION_COOKIE,
        sid,
        max_age=s.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=s.SESSION_COOKIE_SECURE,
        path="/",
    )


def build_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])
    session_repo = SessionRepo(db, max_age_seconds=get_settings().SESSION_MAX_AGE)

    @router.get("/status")
    async def status(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        s = get_settings()
        configured = is_configured()
        setup_guide = None if configured else {
            "steps": [
                "Open Google Cloud Console → APIs & Services → Credentials",
                "Create OAuth 2.0 Client ID (Web application)",
                f"Add authorized redirect URI: {s.OAUTH_REDIRECT_URI or '(set OAUTH_REDIRECT_URI in backend/.env)'}",
                "Enable YouTube Data API v3",
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in backend/.env, then restart backend",
            ],
            "redirect_uri": s.OAUTH_REDIRECT_URI,
        }
        user = None
        sess = await _get_valid_session(db, sid)
        if sess:
            u = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0})
            if u:
                creator = await db.creators.find_one({"user_id": u["id"]}, {"_id": 0})
                youtube = None
                if creator:
                    youtube = await db.connected_platforms.find_one(
                        {"creator_id": creator["id"], "platform": "youtube"}, {"_id": 0}
                    )
                user = {
                    "id": u["id"],
                    "name": u.get("name"),
                    "email": u.get("email"),
                    "picture": u.get("picture"),
                    "youtube_connected": bool(youtube and youtube.get("connection_status") == "connected"),
                }
        return {"configured": configured, "setup_guide": setup_guide, "user": user}

    @router.get("/google/login")
    async def google_login():
        from core.errors import AppError, Codes
        if not is_configured():
            raise AppError(Codes.NOT_CONFIGURED, "Google OAuth not configured — check /api/auth/status.", status_code=400)
        state = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        await db.oauth_states.insert_one({
            "state": state,
            "flow": "login",
            "created_at": now.isoformat(),
            "created_at_ts": now,
        })
        return RedirectResponse(_oauth_url(IDENTITY_SCOPES, state))

    @router.get("/youtube/connect")
    async def youtube_connect(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        from core.errors import AppError, Codes
        if not is_configured():
            raise AppError(Codes.NOT_CONFIGURED, "Google OAuth not configured — check /api/auth/status.", status_code=400)
        sess = await _get_valid_session(db, sid)
        if not sess:
            raise AppError(Codes.UNAUTHENTICATED, "Sign in before connecting YouTube", status_code=401)
        state = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        await db.oauth_states.insert_one({
            "state": state,
            "flow": "youtube_connect",
            "user_id": sess["user_id"],
            "created_at": now.isoformat(),
            "created_at_ts": now,
        })
        return RedirectResponse(_oauth_url(YOUTUBE_SCOPES, state, force_consent=True))

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

        created = st.get("created_at_ts")
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created and datetime.now(timezone.utc) - created > timedelta(minutes=STATE_TTL_MINUTES):
            return RedirectResponse(f"{fe}/?auth_error=expired_state")

        flow = st.get("flow", "login")
        async with httpx.AsyncClient(timeout=15) as client:
            tk = await client.post(TOKEN_URL, data={
                "code": code,
                "client_id": s.GOOGLE_CLIENT_ID,
                "client_secret": s.GOOGLE_CLIENT_SECRET,
                "redirect_uri": s.OAUTH_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            if tk.status_code != 200:
                log.warning("token_exchange_failed status=%s flow=%s", tk.status_code, flow)
                return RedirectResponse(f"{fe}/?auth_error=token_exchange_failed")
            tokens = tk.json()
            access_token = tokens.get("access_token")
            if not access_token:
                return RedirectResponse(f"{fe}/?auth_error=missing_access_token")

            ui_resp = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            if ui_resp.status_code != 200:
                return RedirectResponse(f"{fe}/?auth_error=userinfo_failed")
            uinfo = ui_resp.json()
            google_sub = uinfo.get("sub")
            if not google_sub:
                return RedirectResponse(f"{fe}/?auth_error=missing_google_sub")

            user_repo = UserRepo(db)
            ws_repo = WorkspaceRepo(db)
            creator_repo = CreatorRepo(db)
            platform_repo = PlatformRepo(db)
            cred_repo = CredentialRepo(db)

            if flow == "login":
                user = await user_repo.upsert_by_google_sub(google_sub, {
                    "email": uinfo.get("email"),
                    "name": uinfo.get("name"),
                    "picture": uinfo.get("picture"),
                })
                workspace = await ws_repo.create_owner_workspace(user.id, user.name or "Workspace")
                await creator_repo.upsert_for_user(user.id, workspace.id, {
                    "display_name": user.name or "Creator",
                    "avatar_url": user.picture,
                })
                sid = secrets.token_urlsafe(32)
                await session_repo.create(sid, user.id, user.email, user.name)
                resp = RedirectResponse(f"{fe}/onboarding?login=1")
                _set_session_cookie(resp, sid)
                return resp

            if flow != "youtube_connect":
                return RedirectResponse(f"{fe}/?auth_error=unknown_flow")

            session_user_id = st.get("user_id")
            user = await user_repo.get(session_user_id) if session_user_id else None
            if not user:
                return RedirectResponse(f"{fe}/?auth_error=session_user_missing")
            if user.google_sub and user.google_sub != google_sub:
                return RedirectResponse(f"{fe}/?auth_error=google_account_mismatch")

            creator = await creator_repo.get_by_user(user.id)
            if not creator:
                return RedirectResponse(f"{fe}/?auth_error=creator_missing")

            ch_resp = await client.get(
                YT_CHANNELS_URL,
                params={"part": "snippet,statistics,contentDetails", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ch_resp.status_code != 200:
                log.warning("youtube_channel_fetch_failed status=%s user=%s", ch_resp.status_code, user.id)
                return RedirectResponse(f"{fe}/app/dna?auth_error=youtube_fetch_failed")
            items = ch_resp.json().get("items") or []
            if not items:
                return RedirectResponse(f"{fe}/app/dna?auth_error=no_youtube_channel")
            channel = items[0]

            cp = await platform_repo.upsert(
                creator.id,
                "youtube",
                google_sub,
                {
                    "external_channel_id": channel["id"],
                    "display_name": channel["snippet"]["title"],
                    "handle": channel["snippet"].get("customUrl") or channel["snippet"]["title"],
                    "metadata": {
                        "subscribers": int(channel.get("statistics", {}).get("subscriberCount", 0)),
                        "video_count": int(channel.get("statistics", {}).get("videoCount", 0)),
                    },
                    "connection_status": "connected",
                    "connected_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            old_cred = await cred_repo.get(cp.id)
            refresh_token = tokens.get("refresh_token")
            encrypted_refresh = encrypt(refresh_token) if refresh_token else (
                old_cred.encrypted_refresh_token if old_cred else None
            )
            expires_at = None
            if tokens.get("expires_in"):
                expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(tokens["expires_in"]))).isoformat()
            cred = PlatformCredential(
                connected_platform_id=cp.id,
                encrypted_access_token=encrypt(access_token),
                encrypted_refresh_token=encrypted_refresh,
                expires_at=expires_at,
                scopes=YOUTUBE_SCOPES.split(),
            )
            await cred_repo.upsert(cp.id, cred)
            return RedirectResponse(f"{fe}/app/dna?connected=1")

    @router.post("/youtube/disconnect")
    async def youtube_disconnect(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        from core.errors import AppError, Codes
        sess = await _get_valid_session(db, sid)
        if not sess:
            raise AppError(Codes.UNAUTHENTICATED, "Sign in to disconnect YouTube", status_code=401)
        creator = await CreatorRepo(db).get_by_user(sess["user_id"])
        if not creator:
            raise AppError(Codes.NOT_FOUND, "Creator profile not found", status_code=404)
        cp = await PlatformRepo(db).get_for_creator(creator.id, "youtube")
        if not cp:
            return {"ok": True, "already_disconnected": True}
        await CredentialRepo(db).delete(cp.id)
        await PlatformRepo(db).mark_disconnected(cp.id)
        return {"ok": True}

    @router.post("/logout")
    async def logout(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        if sid:
            await session_repo.revoke(sid)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(SESSION_COOKIE, path="/")
        return resp

    return router


async def current_user(db, sid: Optional[str]):
    """Legacy helper kept for backward compatibility with features.py."""
    sess = await _get_valid_session(db, sid)
    if not sess:
        return None
    u = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0})
    if not u:
        return None
    return {"id": u["id"], "email": u.get("email"), "name": u.get("name"), "picture": u.get("picture")}
