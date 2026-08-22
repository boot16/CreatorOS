"""
CreatorOS backend API tests
Covers:
- Root/health
- Creator DNA (Alex, Sarah)
- Opportunities list + detail (deterministic score + LLM why_bullets)
- Trends list, filter, detail (LLM explanation)
- Compatibility
- Idea Lab (primary LLM feature)
- Collab proposal
- LLM cache latency for opportunity detail
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

# Reasonable LLM timeout (first hit can be 4-8s)
LLM_TIMEOUT = 60


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- Root ----------
class TestRoot:
    def test_root_service(self, s):
        r = s.get(f"{API}/", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("service") == "CreatorOS"


# ---------- Creator DNA ----------
class TestCreator:
    def test_alex_full_dna(self, s):
        r = s.get(f"{API}/creators/alex-morgan", timeout=15)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["id"] == "alex-morgan"
        assert len(c["pillars"]) == 5
        assert len(c["formats"]) == 5
        assert isinstance(c["style"], dict) and c["style"]
        assert len(c["audience_interests"]) == 5
        assert len(c["historical_videos"]) == 20

    def test_sarah_dna(self, s):
        r = s.get(f"{API}/creators/sarah-chen", timeout=15)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["id"] == "sarah-chen"
        assert c["name"] == "Sarah Chen"

    def test_unknown_creator_404(self, s):
        r = s.get(f"{API}/creators/nobody", timeout=15)
        assert r.status_code == 404


# ---------- Opportunities ----------
class TestOpportunities:
    def test_list_alex_opportunities(self, s):
        r = s.get(f"{API}/creators/alex-morgan/opportunities", timeout=15)
        assert r.status_code == 200, r.text
        arr = r.json()
        assert isinstance(arr, list)
        assert len(arr) == 5
        for o in arr:
            assert isinstance(o.get("score"), (int, float))
            assert o.get("trend") and o["trend"].get("id")

    def test_opp1_score_and_bullets(self, s):
        r = s.get(f"{API}/opportunities/opp-1", timeout=LLM_TIMEOUT)
        assert r.status_code == 200, r.text
        o = r.json()
        # deterministic score
        assert o["score"] == 92, f"Expected 92 got {o['score']}"
        # LLM bullets
        bullets = o.get("why_bullets")
        assert isinstance(bullets, list), f"why_bullets not a list: {bullets}"
        assert len(bullets) == 4, f"expected 4 bullets got {len(bullets)}: {bullets}"
        for b in bullets:
            assert isinstance(b, str) and len(b.strip()) > 0

    def test_opp1_llm_cache_fast_second_hit(self, s):
        # Prime cache
        s.get(f"{API}/opportunities/opp-1", timeout=LLM_TIMEOUT)
        t0 = time.time()
        r = s.get(f"{API}/opportunities/opp-1", timeout=15)
        elapsed_ms = (time.time() - t0) * 1000
        assert r.status_code == 200
        # Cache expectation is <500ms but network to preview URL can add latency
        assert elapsed_ms < 2000, f"Cached hit too slow: {elapsed_ms:.0f}ms"
        print(f"Cached opp-1 latency: {elapsed_ms:.0f}ms")


# ---------- Trends ----------
class TestTrends:
    def test_trends_list(self, s):
        r = s.get(f"{API}/trends", timeout=15)
        assert r.status_code == 200, r.text
        arr = r.json()
        assert len(arr) == 8

    def test_trends_filter_ai(self, s):
        r = s.get(f"{API}/trends", params={"category": "AI"}, timeout=15)
        assert r.status_code == 200
        arr = r.json()
        assert len(arr) >= 1
        assert all(t["category"].lower() == "ai" for t in arr)

    def test_trend_ai_agents_detail(self, s):
        r = s.get(f"{API}/trends/ai-agents", timeout=LLM_TIMEOUT)
        assert r.status_code == 200, r.text
        data = r.json()
        expl = data.get("explanation")
        assert isinstance(expl, dict)
        for k in ("why", "related", "audience"):
            assert k in expl, f"missing {k} in explanation: {expl}"
        assert data.get("linked_opportunity_id") == "opp-2"


# ---------- Compatibility ----------
class TestCompatibility:
    def test_compat_alex_sarah(self, s):
        r = s.get(f"{API}/compatibility/alex-morgan/sarah-chen", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["overall"] == 92
        bd = data["breakdown"]
        for k in ("AudienceCompat", "TopicCompat", "ContentComplementarity",
                  "CreatorSizeCompat", "FormatCompat"):
            assert k in bd

    def test_compat_reversed_pair_also_works(self, s):
        r = s.get(f"{API}/compatibility/sarah-chen/alex-morgan", timeout=15)
        assert r.status_code == 200


# ---------- Idea Lab (primary AI feature) ----------
class TestIdeaLab:
    def test_idea_lab_opp1(self, s):
        r = s.post(f"{API}/idea-lab", json={"opportunity_id": "opp-1"}, timeout=LLM_TIMEOUT)
        assert r.status_code == 200, r.text
        data = r.json()
        # required fields
        concept = data.get("concept")
        titles = data.get("titles")
        hooks = data.get("hooks")
        structure = data.get("structure")

        assert isinstance(concept, str) and len(concept.strip()) > 20, f"bad concept: {concept}"
        assert isinstance(titles, list) and len(titles) == 4, f"titles count: {titles}"
        assert isinstance(hooks, list) and len(hooks) == 3, f"hooks count: {hooks}"
        assert isinstance(structure, list) and len(structure) == 5, f"structure: {structure}"
        for t in titles:
            assert isinstance(t, str) and len(t.strip()) > 0
        for h in hooks:
            assert isinstance(h, str) and len(h.strip()) > 0
        for b in structure:
            assert isinstance(b, str) and len(b.strip()) > 0
        # not an echo of the trivial title
        assert titles[0].strip().lower() != "i replaced my first employee with an ai agent — 30 day log"

        print("IDEA LAB SAMPLE ---")
        print("concept:", concept[:200])
        print("titles:", titles)
        print("hooks:", hooks)
        print("structure:", structure)


# ---------- Collab proposal ----------
class TestCollab:
    def test_collab_proposal(self, s):
        payload = {
            "from_creator_id": "alex-morgan",
            "to_creator_id": "sarah-chen",
            "message": "TEST_ collab intro message",
        }
        r = s.post(f"{API}/collab-proposal", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "sent"
