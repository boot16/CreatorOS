"""Symmetric encryption for platform credentials (OAuth tokens)."""
from cryptography.fernet import Fernet, InvalidToken
from core.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().APP_ENCRYPTION_KEY
    if not key:
        raise RuntimeError("APP_ENCRYPTION_KEY not configured — cannot encrypt/decrypt platform credentials")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return None
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if ciphertext is None:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt platform credential — key rotation may be needed") from exc
