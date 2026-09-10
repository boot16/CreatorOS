"""Central runtime settings loaded once from environment."""
import os
from functools import lru_cache


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
        self.FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
        self.SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", "2592000"))

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
            if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET:
                issues.append("Google OAuth credentials are required in production")
        return issues


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
