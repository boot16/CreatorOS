"""YouTube access-token refresh — reuses the stored encrypted refresh_token."""
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx

from core.config import get_settings
from core.encryption import encrypt, decrypt
from core.errors import AppError, Codes
from core.logging import get_logger
from models.domain import PlatformCredential
from repositories import CredentialRepo

log = get_logger("services.youtube_tokens")

TOKEN_URL = "https://oauth2.googleapis.com/token"


async def refresh_access_token(db, connected_platform_id: str) -> Optional[str]:
    """Exchange the stored refresh_token for a new access_token.

    Returns the new access_token, or None if refresh not possible (no refresh_token, expired grant).
    Callers should retry the original request once with the returned token.
    """
    repo = CredentialRepo(db)
    cred = await repo.get(connected_platform_id)
    if not cred or not cred.encrypted_refresh_token:
        return None
    settings = get_settings()
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return None
    refresh_token = decrypt(cred.encrypted_refresh_token)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        if r.status_code != 200:
            log.warning(f"token_refresh_failed status={r.status_code} cp={connected_platform_id}")
            return None
        data = r.json()
    new_access = data.get("access_token")
    if not new_access:
        return None
    expires_in = int(data.get("expires_in", 3600))
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    updated = PlatformCredential(
        id=cred.id, connected_platform_id=cred.connected_platform_id,
        encrypted_access_token=encrypt(new_access),
        encrypted_refresh_token=cred.encrypted_refresh_token,
        expires_at=expires_at, scopes=cred.scopes,
    )
    await repo.upsert(connected_platform_id, updated)
    log.info(f"token_refreshed cp={connected_platform_id}")
    return new_access
