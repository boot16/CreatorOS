"""In-memory sliding-window rate limiter. Swap for Redis later without changing call sites."""
import time
from collections import defaultdict, deque
from threading import Lock

from core.errors import AppError, Codes


class RateLimiter:
    def __init__(self):
        self._store: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        """Raise AppError with RATE_LIMITED if key exceeded limit in window."""
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            q = self._store[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                retry_after = int(q[0] + window_seconds - now) + 1
                raise AppError(
                    code=Codes.RATE_LIMITED,
                    message=f"Rate limit exceeded. Retry in {retry_after}s.",
                    status_code=429,
                    meta={"retry_after": retry_after, "limit": limit, "window_seconds": window_seconds},
                )
            q.append(now)


_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter


# Preset budgets (per identity per window seconds)
BUDGETS = {
    "llm_idea_lab": (20, 3600),        # 20 idea-lab generations per hour
    "llm_script_refine": (30, 3600),   # 30 script refinements per hour
    "llm_studio_chat": (60, 3600),     # 60 chat messages per hour
    "oauth_login": (10, 600),          # 10 OAuth kicks per 10 minutes
    "collab_proposal": (10, 3600),
}
