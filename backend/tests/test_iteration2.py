"""
CreatorOS iteration 2 backend API tests.
Covers:
- Google OAuth unconfigured fallback (auth/status, auth/google/login 400)
- Idea Lab regenerate flag busts cache (fresh titles)
- Shortlist CRUD with X-Client-Id header (add/get/delete)
- DNA card PNG endpoint (image bytes)
- Assistant chat streaming + history persistence
"""

import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

LLM_TIMEOUT = 90


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- Google OAuth (unconfigured fallback path) ----------
class TestAuthStatus:
    def test_auth_status_unconfigured(self, s):
        r = s.get(f"{API}/auth/status", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("configured") is False, f"expected configured=False, got: {data}"
        sg = data.get("setup_guide")
        assert isinstance(sg, dict), f"setup_guide missing: {data}"
        steps = sg.get("steps")
        assert isinstance(steps, list) and len(steps) == 5, f"expected 5 steps got: {steps}"
        assert all(isinstance(x, str) and len(x) > 0 for x in steps)
        # redirect_uri present and pointing to callback
        r_uri = sg.get("redirect_uri", "")
        assert "/api/auth/google/callback" in r_uri, f"bad redirect_uri: {r_uri}"
        assert data.get("user") is None

    def test_google_login_unconfigured_returns_400(self, s):
        # allow_redirects=False in case some future code adds a redirect
        r = s.get(f"{API}/auth/google/login", timeout=15, allow_redirects=False)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
        assert "not configured" in r.text.lower() or "configured" in r.text.lower(), r.text


# ---------- Idea Lab regenerate busts cache ----------
class TestIdeaLabRegenerate:
    def test_regenerate_returns_different_titles(self, s):
        # Prime cache
        r1 = s.post(f"{API}/idea-lab", json={"opportunity_id": "opp-1"}, timeout=LLM_TIMEOUT)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        titles1 = d1.get("titles")
        assert isinstance(titles1, list) and len(titles1) == 4, titles1

        # Cached hit should be fast
        t0 = time.time()
        r2 = s.post(f"{API}/idea-lab", json={"opportunity_id": "opp-1"}, timeout=30)
        elapsed_ms = (time.time() - t0) * 1000
        assert r2.status_code == 200
        assert r2.json().get("titles") == titles1, "cached second call should return same titles"
        assert elapsed_ms < 3000, f"cached hit too slow: {elapsed_ms:.0f}ms"

        # Regenerate must invoke LLM and return different titles
        r3 = s.post(
            f"{API}/idea-lab",
            json={"opportunity_id": "opp-1", "regenerate": True},
            timeout=LLM_TIMEOUT,
        )
        assert r3.status_code == 200, r3.text
        d3 = r3.json()
        titles3 = d3.get("titles")
        assert isinstance(titles3, list) and len(titles3) == 4
        # Not identical arrays
        assert titles3 != titles1, f"regenerate returned same titles: {titles3}"
        # Also validate structure of regen response
        for k in ("concept", "titles", "hooks", "structure"):
            assert k in d3, f"missing key {k}"
        print("BEFORE regen titles:", titles1)
        print("AFTER  regen titles:", titles3)


# ---------- Shortlist per-client via X-Client-Id ----------
class TestShortlist:
    def test_shortlist_crud_flow(self, s):
        cid = f"TEST_{uuid.uuid4().hex[:12]}"
        headers = {"X-Client-Id": cid, "Content-Type": "application/json"}

        # Empty at start
        r0 = requests.get(f"{API}/shortlist", headers=headers, timeout=15)
        assert r0.status_code == 200
        assert r0.json() == []

        # Add
        ra = requests.post(
            f"{API}/shortlist",
            headers=headers,
            json={"opportunity_id": "opp-1"},
            timeout=15,
        )
        assert ra.status_code == 200, ra.text
        assert ra.json().get("ok") is True

        # Get returns 1 with embedded opportunity payload
        rg = requests.get(f"{API}/shortlist", headers=headers, timeout=30)
        assert rg.status_code == 200, rg.text
        arr = rg.json()
        assert isinstance(arr, list) and len(arr) == 1, arr
        item = arr[0]
        assert item["opportunity_id"] == "opp-1"
        opp = item.get("opportunity")
        assert isinstance(opp, dict), f"missing opportunity payload: {item}"
        assert opp.get("id") == "opp-1"
        assert "score" in opp and "title" in opp

        # Idempotent add
        ra2 = requests.post(
            f"{API}/shortlist",
            headers=headers,
            json={"opportunity_id": "opp-1"},
            timeout=15,
        )
        assert ra2.status_code == 200
        rg2 = requests.get(f"{API}/shortlist", headers=headers, timeout=15)
        assert len(rg2.json()) == 1, "duplicate should not create second row"

        # Delete
        rd = requests.delete(f"{API}/shortlist/opp-1", headers=headers, timeout=15)
        assert rd.status_code == 200, rd.text
        d = rd.json()
        assert d.get("removed") == 1

        # Get 0
        rg3 = requests.get(f"{API}/shortlist", headers=headers, timeout=15)
        assert rg3.status_code == 200
        assert rg3.json() == []

    def test_shortlist_isolation_between_clients(self, s):
        cid_a = f"TEST_A_{uuid.uuid4().hex[:8]}"
        cid_b = f"TEST_B_{uuid.uuid4().hex[:8]}"
        hA = {"X-Client-Id": cid_a, "Content-Type": "application/json"}
        hB = {"X-Client-Id": cid_b, "Content-Type": "application/json"}
        try:
            r = requests.post(f"{API}/shortlist", headers=hA, json={"opportunity_id": "opp-2"}, timeout=15)
            assert r.status_code == 200
            rb = requests.get(f"{API}/shortlist", headers=hB, timeout=15)
            assert rb.status_code == 200
            assert rb.json() == [], "client B should not see client A's shortlist"
        finally:
            requests.delete(f"{API}/shortlist/opp-2", headers=hA, timeout=15)


# ---------- DNA card PNG ----------
class TestDnaCard:
    def test_dna_card_png_success(self, s):
        r = s.get(f"{API}/dna-card/alex-morgan.png", timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("image/png"), r.headers
        # PNG signature
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n", "not a valid PNG header"
        size = len(r.content)
        assert size > 20 * 1024, f"png too small: {size} bytes"
        print(f"DNA card size: {size} bytes")

    def test_dna_card_not_found(self, s):
        r = s.get(f"{API}/dna-card/nonexistent.png", timeout=15)
        assert r.status_code == 404, r.text


# ---------- Assistant chat (streaming) ----------
class TestAssistant:
    def test_assistant_streaming_and_history(self, s):
        session_id = f"TEST_s_{uuid.uuid4().hex[:8]}"
        payload = {
            "session_id": session_id,
            "creator_id": "alex-morgan",
            "messages": [{"role": "user", "content": "Give me 2 title ideas that fit my DNA. Number them 1 and 2."}],
        }
        with requests.post(
            f"{API}/assistant/chat",
            json=payload,
            stream=True,
            timeout=LLM_TIMEOUT,
        ) as r:
            assert r.status_code == 200, r.text[:200]
            ct = r.headers.get("content-type", "")
            assert ct.startswith("text/plain"), f"expected text/plain got: {ct}"
            chunks = []
            for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    chunks.append(chunk if isinstance(chunk, str) else chunk.decode("utf-8", errors="ignore"))
                if sum(len(c) for c in chunks) > 4000:
                    break
            body = "".join(chunks)
        assert len(body) > 50, f"stream too short: {body!r}"
        # Should include creator-relevant real content (title, video, or a numbered list)
        lb = body.lower()
        assert any(kw in lb for kw in ["title", "video", "alex", "1.", "1)", "hook"]), f"reply seems unrelated: {body[:400]}"
        print("STREAM SAMPLE:", body[:400])

        # History
        time.sleep(1)  # small settle for async DB write
        rh = requests.get(f"{API}/assistant/history/{session_id}", timeout=15)
        assert rh.status_code == 200
        hist = rh.json()
        assert isinstance(hist, list) and len(hist) >= 1
        roles = [h["role"] for h in hist]
        assert "user" in roles, f"user turn missing from history: {hist}"
        # first user content matches
        user_msg = next(h for h in hist if h["role"] == "user")
        assert "title" in user_msg["content"].lower(), user_msg
