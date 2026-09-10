"""Regression tests for the split Google-login / YouTube-connect auth foundation."""
import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_auth_stabilization")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-secret")
os.environ.setdefault("OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")

from core.config import get_settings
from auth_google import _oauth_url, IDENTITY_SCOPES, YOUTUBE_SCOPES


def test_local_cookie_is_not_secure_by_default(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "demo")
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    get_settings.cache_clear()
    assert get_settings().SESSION_COOKIE_SECURE is False


def test_production_cookie_is_secure_by_default(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "production")
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    get_settings.cache_clear()
    assert get_settings().SESSION_COOKIE_SECURE is True


def test_google_login_uses_identity_only_scopes(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    get_settings.cache_clear()
    url = _oauth_url(IDENTITY_SCOPES, "state-1")
    assert "youtube.readonly" not in url
    assert "openid" in url
    assert "email" in url
    assert "profile" in url


def test_youtube_connect_requests_readonly_and_offline_access(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    get_settings.cache_clear()
    url = _oauth_url(YOUTUBE_SCOPES, "state-2", force_consent=True)
    assert "youtube.readonly" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url


def test_production_validation_requires_selected_llm_key(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("CORS_ORIGINS", "https://creatoros.example")
    monkeypatch.setenv("FRONTEND_URL", "https://creatoros.example")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "https://api.creatoros.example/api/auth/google/callback")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    issues = get_settings().validate_production()
    assert "API key required for LLM_PROVIDER=gemini" in issues
