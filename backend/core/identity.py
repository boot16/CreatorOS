"""Identity resolution — the single source of truth for who is calling.

Never trust caller-provided IDs. Always resolve identity server-side from session cookie.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

from fastapi import Cookie
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import get_settings
from core.errors import AppError, Codes
from core.logging import set_user_id

SESSION_COOKIE = "creatoros_sid"
DEMO_USER_ID = "demo-user"
DEMO_WORKSPACE_ID = "demo-workspace"
DEMO_CREATOR_ID = "alex-morgan"


@dataclass
class CurrentUser:
    user_id: str
    creator_id: Optional[str]
    workspace_id: Optional[str]
    is_authenticated: bool
    is_demo: bool
    email: Optional[str] = None
    name: Optional[str] = None


async def _validate_session(db: AsyncIOMotorDatabase, sid: str) -> Optional[dict]:
    """Return session dict if valid + not expired, else None."""
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


async def resolve_identity(db: AsyncIOMotorDatabase, sid: Optional[str]) -> CurrentUser:
    """Resolve identity from session cookie.

    Rules:
    - Authenticated session → real identity (production-safe)
    - No session + DATA_MODE=demo → demo identity (Alex workspace)
    - No session + DATA_MODE=production → anonymous, not authenticated
    """
    settings = get_settings()
    sess = await _validate_session(db, sid) if sid else None
    if sess:
        user_id = sess["user_id"]
        creator = await db.creators.find_one({"user_id": user_id}, {"_id": 0})
        set_user_id(user_id)
        return CurrentUser(
            user_id=user_id,
            creator_id=(creator["id"] if creator else None),
            workspace_id=(creator["workspace_id"] if creator else None),
            is_authenticated=True,
            is_demo=False,
            email=sess.get("email"),
            name=sess.get("name"),
        )
    if settings.is_demo:
        set_user_id(DEMO_USER_ID)
        return CurrentUser(
            user_id=DEMO_USER_ID,
            creator_id=DEMO_CREATOR_ID,
            workspace_id=DEMO_WORKSPACE_ID,
            is_authenticated=False,
            is_demo=True,
            name="Alex Morgan (demo)",
        )
    # production, no session
    return CurrentUser(
        user_id="anonymous",
        creator_id=None,
        workspace_id=None,
        is_authenticated=False,
        is_demo=False,
    )


def require_auth(user: CurrentUser) -> None:
    if not user.is_authenticated and not user.is_demo:
        raise AppError(Codes.UNAUTHENTICATED, "Sign in to continue", status_code=401)


def require_real_auth(user: CurrentUser) -> None:
    """For endpoints that MUST have a real user (mutations affecting real accounts)."""
    if not user.is_authenticated:
        raise AppError(Codes.UNAUTHENTICATED, "Sign in with your account to continue", status_code=401)


def require_creator(user: CurrentUser) -> str:
    if not user.creator_id:
        raise AppError(Codes.NOT_FOUND, "No creator profile associated with this account", status_code=404)
    return user.creator_id


def require_workspace(user: CurrentUser) -> str:
    if not user.workspace_id:
        raise AppError(Codes.NOT_FOUND, "No workspace associated with this account", status_code=404)
    return user.workspace_id
