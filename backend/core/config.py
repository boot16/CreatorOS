"""Central runtime settings loaded once from environment."""
import os
from functools import lru_cache


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    MONGO_URL: str
    DB_NAME: str
    DATA_MODE: str
    EMERGENT_LLM_KEY: str
    ANTHROPIC_API_KEY: str
    GROQ_API_KEY: str
    GEMINI_API_KEY: str
    LLM_PROVIDER: str  # anthropic | groq | gemini
    LLM_MODEL: str     # optional override; falls back to a sensible default per provider
    APP_ENCRYPTION_KEY: str
    CORS_ORIGINS: list
    FRONTEND_URL: str
    SESSION_MAX_AGE: int
    SESSION_COOKIE_SECURE: bool

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    OAUTH_REDIRECT_URI: str

    SLACK_WEBHOOK_URL: str

    def __init__(self):
        self.MONGO_URL = os.environ["MONGO_URL"]
        self.DB_NAME = os.environ["DB_NAME"]
        self.DATA_MODE = os.environ.get("DATA_MODE", "demo").lower()
        self.EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
        self.ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
        self.GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
        self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
        self.LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
        self.LLM_MODEL = os.environ.get("LLM_MODEL", "").strip()
        self.APP_ENCRYPTION_KEY = os.environ.get("APP_ENCRYPTION_KEY", "")
        raw_cors = os.environ.get("CORS_ORIGINS", "*")
        self.CORS_ORIGINS = [o.strip() for o in raw_cors.split(",") if o.strip()]
        self.FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
        self.SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", "2592000"))
        # Secure cookies are mandatory in production, but break localhost over plain HTTP.
        self.SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", self.DATA_MODE == "production")

        self.GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        self.GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        self.OAUTH_REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "").strip()

        self.SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

    @property
    def is_production(self) -> bool:
        return self.DATA_MODE == "production"

    @property
    def is_demo(self) -> bool:
        return self.DATA_MODE == "demo"

    def validate_production(self) -> list:
        """Return list of blockers preventing safe production startup."""
        issues = []
        if self.is_production:
            if "*" in self.CORS_ORIGINS:
                issues.append("CORS_ORIGINS cannot include '*' in production")
            if not self.APP_ENCRYPTION_KEY:
                issues.append("APP_ENCRYPTION_KEY is required in production")
            if not self.FRONTEND_URL:
                issues.append("FRONTEND_URL is required in production")
            if not self.SESSION_COOKIE_SECURE:
                issues.append("SESSION_COOKIE_SECURE must be true in production")
            if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET or not self.OAUTH_REDIRECT_URI:
                issues.append("Google OAuth credentials and redirect URI are required in production")
            provider_keys = {
                "anthropic": self.ANTHROPIC_API_KEY,
                "groq": self.GROQ_API_KEY,
                "gemini": self.GEMINI_API_KEY,
            }
            if self.LLM_PROVIDER not in provider_keys:
                issues.append("LLM_PROVIDER must be anthropic, groq, or gemini")
            elif not provider_keys[self.LLM_PROVIDER]:
                issues.append(f"API key required for LLM_PROVIDER={self.LLM_PROVIDER}")
        return issues


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
