"""Test-time setup — loads /app/frontend/.env so REACT_APP_BACKEND_URL is available
for the iteration-2/3 backend tests without a manual `export` step.

Keep this cheap and side-effect only.
"""
import os
from pathlib import Path


def _load_env_file(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


# Load frontend .env so REACT_APP_BACKEND_URL is available for tests hitting the preview URL.
_load_env_file(Path("/app/frontend/.env"))
# Backend .env is loaded by server.py at import; ensure it's also set for standalone tests.
_load_env_file(Path("/app/backend/.env"))


# Session-scoped in-process TestClient — motor's AsyncIOMotorClient binds to one event loop, so
# a single client shared across ALL tests avoids "Event loop is closed" between modules.
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def inproc_client():
    """Session-scoped in-process TestClient. Motor's AsyncIOMotorClient (created at
    server.py import time) binds to the first event loop it sees, so we keep a single
    loop alive for the duration of the run. Async tests in this suite use their own
    dedicated Motor client fixtures and do NOT reuse this one."""
    from server import app
    with TestClient(app) as c:
        yield c
