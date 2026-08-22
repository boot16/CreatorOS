"""
CreatorOS iteration 3 backend API tests.

Covers 15 new endpoints:
- Team Handoff:   GET /handoff/status, GET /handoff/brief/{opp}, POST /handoff/slack (unconfigured 400)
- Script Drafts:  POST /scripts (Claude real draft), GET /scripts, GET /scripts/{id},
                  PATCH /scripts/{id}, POST /scripts/{id}/refine (Claude), DELETE /scripts/{id}
- Weekly Calendar: POST /calendar, GET /calendar (with embedded opportunity),
                   PATCH /calendar/{id}, DELETE /calendar/{id}
- Real DNA (auth-gated fallbacks): GET /me/creator returns 401 unauth (NOT 404),
                                    GET /me/opportunities returns 401 unauth
"""

import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

LLM_TIMEOUT = 120  # Claude script drafting takes ~8-15s


# ---------------- Team Handoff ----------------
class TestHandoff:
    def test_handoff_status_slack_unconfigured(self):
        r = requests.get(f"{API}/handoff/status", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        # Slack unconfigured branch
        assert isinstance(d.get("slack"), dict), d
        assert d["slack"]["configured"] is False, f"expected configured=False, got: {d['slack']}"
        sg = d["slack"].get("setup_guide")
        assert isinstance(sg, dict), f"setup_guide missing: {d}"
        steps = sg.get("steps")
        assert isinstance(steps, list) and len(steps) == 5, f"expected 5 steps got: {steps}"
        assert all(isinstance(s, str) and len(s) > 0 for s in steps)
        # Email mailto branch
        email = d.get("email")
        assert isinstance(email, dict) and email.get("configured") is True
        assert email.get("mode") == "mailto", email

    def test_handoff_brief_returns_markdown_with_expected_sections(self):
        r = requests.get(f"{API}/handoff/brief/opp-1", timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("markdown", "subject", "opportunity_id"):
            assert k in d, f"missing key {k} in {d.keys()}"
        assert d["opportunity_id"] == "opp-1"
        assert d["subject"].startswith("[Brief]"), d["subject"]
        md = d["markdown"]
        # Required content
        assert "# I Replaced My First Employee" in md, md[:400]
        assert "Score:" in md
        assert "## Why this fits" in md
        assert "## Score breakdown" in md

    def test_handoff_brief_404_for_bad_opp(self):
        r = requests.get(f"{API}/handoff/brief/does-not-exist", timeout=15)
        assert r.status_code == 404, r.text

    def test_handoff_slack_400_when_unconfigured(self):
        r = requests.post(
            f"{API}/handoff/slack",
            json={"opportunity_id": "opp-1"},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
        # Message contains 'Slack webhook not configured'
        assert "not configured" in r.text.lower(), r.text


# ---------------- Script Drafts (Claude real output) ----------------
@pytest.fixture(scope="class")
def scripts_client_id():
    return f"TEST_iter3a_{uuid.uuid4().hex[:8]}"


class TestScripts:
    created_ids = []

    def _headers(self, cid):
        return {"X-Client-Id": cid, "Content-Type": "application/json"}

    def test_create_script_returns_real_claude_body(self, scripts_client_id):
        # Warm the idea-lab cache (used by _make_initial_script)
        r_idea = requests.post(
            f"{API}/idea-lab",
            json={"opportunity_id": "opp-1"},
            timeout=LLM_TIMEOUT,
        )
        assert r_idea.status_code == 200, r_idea.text

        r = requests.post(
            f"{API}/scripts",
            headers=self._headers(scripts_client_id),
            json={"opportunity_id": "opp-1"},
            timeout=LLM_TIMEOUT,
        )
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d.get("id") and isinstance(d["id"], str)
        body = d.get("body")
        assert isinstance(body, str), d
        assert len(body) > 1000, f"script body too short ({len(body)} chars): {body[:400]}"
        # Sanity: real claude script should contain script-like anchors (HOOK / BEAT / camera / broll)
        lb = body.lower()
        anchors = ["hook", "beat", "b-roll", "on camera", "camera"]
        matched = [a for a in anchors if a in lb]
        assert len(matched) >= 2, f"body missing script anchors, only found={matched}: {body[:400]}"
        # store for downstream tests
        TestScripts.created_ids.append(d["id"])
        print(f"Created script id={d['id']} body_len={len(body)} anchors={matched}")

    def test_list_scripts_returns_created_item(self, scripts_client_id):
        r = requests.get(f"{API}/scripts", headers=self._headers(scripts_client_id), timeout=15)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1, items
        # list projection excludes body (see features.py:166)
        assert "body" not in items[0], items[0]
        assert items[0].get("id") in TestScripts.created_ids
        assert "title" in items[0]

    def test_get_script_full_doc(self, scripts_client_id):
        sid = TestScripts.created_ids[0]
        r = requests.get(f"{API}/scripts/{sid}", headers=self._headers(scripts_client_id), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == sid
        assert isinstance(d.get("body"), str) and len(d["body"]) > 1000

    def test_patch_script_body_persists(self, scripts_client_id):
        sid = TestScripts.created_ids[0]
        new_body = f"edited-{uuid.uuid4().hex[:6]}"
        rp = requests.patch(
            f"{API}/scripts/{sid}",
            headers=self._headers(scripts_client_id),
            json={"body": new_body},
            timeout=15,
        )
        assert rp.status_code == 200, rp.text
        # verify GET returns the edited body
        rg = requests.get(f"{API}/scripts/{sid}", headers=self._headers(scripts_client_id), timeout=15)
        assert rg.status_code == 200
        assert rg.json()["body"] == new_body

    def test_refine_script_returns_new_body(self, scripts_client_id):
        sid = TestScripts.created_ids[0]
        # First re-create a real body via refine base — use a real script body first
        # Set a substantial body so refine has content to work with
        seed_body = (
            "HOOK: I fired my first employee.\n\n"
            "BEAT 1: The setup — six months ago, I hired Marcus. Great guy. Terrible fit.\n\n"
            "BEAT 2: What actually happened when I let him go and replaced him with three AI agents.\n\n"
            "BEAT 3: The real numbers — time saved, mistakes made, what I learned.\n\n"
            "BEAT 4: What I'd tell any founder considering this."
        )
        requests.patch(
            f"{API}/scripts/{sid}",
            headers=self._headers(scripts_client_id),
            json={"body": seed_body},
            timeout=15,
        )
        before = requests.get(f"{API}/scripts/{sid}", headers=self._headers(scripts_client_id), timeout=15).json()["body"]

        r = requests.post(
            f"{API}/scripts/{sid}/refine",
            headers=self._headers(scripts_client_id),
            json={"instruction": "Make the hook 2x stronger and more specific — cut the fluff."},
            timeout=LLM_TIMEOUT,
        )
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        new_body = d.get("body")
        assert isinstance(new_body, str) and len(new_body) > 100, d
        assert new_body != before, "refine returned same body as before"
        # Persisted?
        after = requests.get(f"{API}/scripts/{sid}", headers=self._headers(scripts_client_id), timeout=15).json()["body"]
        assert after == new_body
        print(f"REFINE: before_len={len(before)} after_len={len(new_body)}")

    def test_delete_script(self, scripts_client_id):
        sid = TestScripts.created_ids[0]
        r = requests.delete(f"{API}/scripts/{sid}", headers=self._headers(scripts_client_id), timeout=15)
        assert r.status_code == 200
        # confirm gone (returns 404)
        rg = requests.get(f"{API}/scripts/{sid}", headers=self._headers(scripts_client_id), timeout=15)
        assert rg.status_code == 404, rg.text


# ---------------- Weekly Calendar ----------------
@pytest.fixture(scope="class")
def cal_client_id():
    return f"TEST_iter3b_{uuid.uuid4().hex[:8]}"


class TestCalendar:
    plan_id = None

    def _headers(self, cid):
        return {"X-Client-Id": cid, "Content-Type": "application/json"}

    def test_add_plan(self, cal_client_id):
        r = requests.post(
            f"{API}/calendar",
            headers=self._headers(cal_client_id),
            json={"opportunity_id": "opp-1", "date": "2026-03-02"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("id") and isinstance(d["id"], str)
        assert d["opportunity_id"] == "opp-1"
        assert d["date"] == "2026-03-02"
        TestCalendar.plan_id = d["id"]

    def test_list_plan_with_embedded_opportunity(self, cal_client_id):
        r = requests.get(f"{API}/calendar", headers=self._headers(cal_client_id), timeout=30)
        assert r.status_code == 200, r.text
        arr = r.json()
        assert isinstance(arr, list) and len(arr) >= 1, arr
        item = next((x for x in arr if x["id"] == TestCalendar.plan_id), None)
        assert item is not None, arr
        opp = item.get("opportunity")
        assert isinstance(opp, dict) and opp.get("id") == "opp-1"
        assert "score" in opp and "trend" in opp

    def test_move_plan(self, cal_client_id):
        r = requests.patch(
            f"{API}/calendar/{TestCalendar.plan_id}",
            headers=self._headers(cal_client_id),
            json={"date": "2026-03-05"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # Verify persisted
        arr = requests.get(f"{API}/calendar", headers=self._headers(cal_client_id), timeout=15).json()
        moved = next(x for x in arr if x["id"] == TestCalendar.plan_id)
        assert moved["date"] == "2026-03-05"

    def test_delete_plan(self, cal_client_id):
        r = requests.delete(
            f"{API}/calendar/{TestCalendar.plan_id}",
            headers=self._headers(cal_client_id),
            timeout=15,
        )
        assert r.status_code == 200
        arr = requests.get(f"{API}/calendar", headers=self._headers(cal_client_id), timeout=15).json()
        assert not any(x["id"] == TestCalendar.plan_id for x in arr)


# ---------------- Real DNA / auth-gated paths ----------------
class TestMeAuthGates:
    def test_me_creator_unauth_returns_401_not_404(self):
        """Critical: must not be 404 (would indicate route collision with /creators/{id})."""
        r = requests.get(f"{API}/me/creator", timeout=15)
        assert r.status_code == 401, (
            f"expected 401 unauth, got {r.status_code} — check route order / path collision "
            f"with /creators/{{id}}. body={r.text[:200]}"
        )

    def test_me_opportunities_unauth_returns_401(self):
        r = requests.get(f"{API}/me/opportunities", timeout=15)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"
