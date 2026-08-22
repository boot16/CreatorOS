"""Team handoff, script drafts, weekly calendar, real-DNA ingest endpoints.

All routes assume the shared `db` (mongo) and helpers imported by server.py.
"""
import os
import uuid
import json
import re
from datetime import datetime, timezone
from typing import Optional, List
from urllib.parse import quote

import httpx
from fastapi import APIRouter, HTTPException, Header, Cookie, Response
from pydantic import BaseModel

from auth_google import SESSION_COOKIE, current_user


def build_router(db, deps):
    """deps carries: get_opportunity, get_creator_data, call_llm, extract_json, WEIGHTS_OPP, OPPORTUNITIES, TRENDS, compute_opportunity_score, ALEX"""
    router = APIRouter()

    def cid(x_client_id: Optional[str], sid: Optional[str]) -> str:
        return sid or x_client_id or "demo-anonymous"

    # ---------------- Team Handoff ----------------
    @router.get("/handoff/status")
    async def handoff_status():
        slack = bool(os.environ.get("SLACK_WEBHOOK_URL", "").strip())
        return {
            "slack": {
                "configured": slack,
                "setup_guide": None if slack else {
                    "steps": [
                        "Go to https://api.slack.com/apps and create a new app (From scratch → any workspace)",
                        "Enable 'Incoming Webhooks' feature",
                        "Click 'Add New Webhook to Workspace' → choose the channel to post to",
                        "Copy the Webhook URL",
                        "Paste it into /app/backend/.env as SLACK_WEBHOOK_URL → restart backend",
                    ],
                },
            },
            "email": {"configured": True, "mode": "mailto"},
        }

    async def _brief_markdown(opp: dict) -> str:
        creator = opp["creator"]
        trend = opp["trend"]
        cached = await db.llm_cache.find_one({"kind": "opp_why", "key": opp["id"]}, {"_id": 0})
        bullets = cached["value"] if cached else []
        lines = [
            f"# {opp['title']}",
            "",
            f"**Score:** {opp['score']}/100  •  **Format:** {opp['format']}  •  **Trend:** {trend['name']} ({trend['stage']}, {'+' if trend['momentum']>=0 else ''}{trend['momentum']}% momentum)",
            "",
            f"For {creator['name']} — {creator['handle']} · {creator['subscribers']:,} subs · {creator['niche']}",
            "",
            "## Why this fits, right now",
        ]
        for b in bullets:
            lines.append(f"- {b}")
        lines += ["", "## Score breakdown"]
        sub = opp["sub_scores"]
        lines.append(f"- Trend Fit: {sub['TrendFit']} (×0.25)")
        lines.append(f"- Creator Fit: {sub['CreatorFit']} (×0.25)")
        lines.append(f"- Historical Format Fit: {sub['HistoricalFormatFit']} (×0.20)")
        lines.append(f"- Audience Fit: {sub['AudienceFit']} (×0.10)")
        lines.append(f"- Freshness: {sub['Freshness']} (×0.10)")
        lines.append(f"- Un-saturation: {100 - sub['Saturation']} (×0.10)")
        lines += ["", f"— Sent from CreatorOS  ·  https://opportunity-feed-6.preview.emergentagent.com/app/opportunity/{opp['id']}"]
        return "\n".join(lines)

    @router.get("/handoff/brief/{opp_id}")
    async def handoff_brief(opp_id: str):
        opp = await deps["get_opportunity"](opp_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        md = await _brief_markdown(opp)
        return {"markdown": md, "subject": f"[Brief] {opp['title']}", "opportunity_id": opp_id}

    class SlackSendRequest(BaseModel):
        opportunity_id: str

    @router.post("/handoff/slack")
    async def handoff_slack(req: SlackSendRequest):
        webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
        if not webhook:
            raise HTTPException(400, "Slack webhook not configured — see /api/handoff/status for setup steps.")
        opp = await deps["get_opportunity"](req.opportunity_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        md = await _brief_markdown(opp)
        payload = {
            "text": f"*New brief from CreatorOS*: {opp['title']}",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": opp["title"]}},
                {"type": "section", "text": {"type": "mrkdwn", "text": md[:2900]}},
            ],
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook, json=payload)
            if r.status_code >= 300:
                raise HTTPException(502, f"Slack error: {r.status_code} {r.text[:200]}")
        return {"ok": True}

    # ---------------- Script Drafts ----------------
    class ScriptCreateRequest(BaseModel):
        opportunity_id: str

    class ScriptUpdateRequest(BaseModel):
        body: Optional[str] = None
        title: Optional[str] = None

    class ScriptRefineRequest(BaseModel):
        instruction: str

    async def _make_initial_script(opp: dict, idea: dict) -> str:
        creator = opp["creator"]
        prompt = (
            f"Write a first-draft YouTube video script for {creator['name']} ({creator['niche']}). "
            f"Voice: {creator['style']['tone']}. Hook style: {creator['style']['hook_style']}. Pace: {creator['style']['pace']}. "
            f"Working title: '{opp['title']}'. Format: {opp['format']}. Trend: {opp['trend']['name']}. "
            f"Concept: {idea.get('concept','')} "
            f"Structure beats: {' | '.join(idea.get('structure',[]))} "
            f"Preferred hook: {(idea.get('hooks') or [''])[0]}. "
            "Write it as a real script with clear sections (HOOK, BEAT 1, BEAT 2, ...), plus [B-ROLL] and [ON CAMERA] notes. "
            "Around 700-900 words. First person. Match the creator's voice exactly — no generic AI phrasing."
        )
        return await deps["call_llm"](
            "You are a top-tier YouTube script writer. Return only the script text, no preamble.",
            prompt, session_id=f"script-{opp['id']}",
        )

    @router.post("/scripts")
    async def create_script(
        req: ScriptCreateRequest,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        opp = await deps["get_opportunity"](req.opportunity_id)
        if not opp:
            raise HTTPException(404, "Opportunity not found")
        idea = await db.llm_cache.find_one({"kind": "idea_lab", "key": req.opportunity_id}, {"_id": 0})
        idea_val = idea["value"] if idea else {"concept": opp["title"], "structure": [], "hooks": []}
        body = await _make_initial_script(opp, idea_val)
        doc = {
            "id": str(uuid.uuid4()),
            "client_id": cid(x_client_id, sid),
            "opportunity_id": req.opportunity_id,
            "title": opp["title"],
            "body": body,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.scripts.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.get("/scripts")
    async def list_scripts(
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        items = await db.scripts.find({"client_id": client_id}, {"_id": 0, "body": 0}).sort("updated_at", -1).to_list(200)
        return items

    @router.get("/scripts/{script_id}")
    async def get_script(
        script_id: str,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        s = await db.scripts.find_one({"id": script_id, "client_id": client_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Script not found")
        return s

    @router.patch("/scripts/{script_id}")
    async def update_script(
        script_id: str,
        req: ScriptUpdateRequest,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        update = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if req.body is not None: update["body"] = req.body
        if req.title is not None: update["title"] = req.title
        r = await db.scripts.update_one({"id": script_id, "client_id": client_id}, {"$set": update})
        if r.matched_count == 0:
            raise HTTPException(404, "Script not found")
        return {"ok": True}

    @router.delete("/scripts/{script_id}")
    async def delete_script(
        script_id: str,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        await db.scripts.delete_one({"id": script_id, "client_id": client_id})
        return {"ok": True}

    @router.post("/scripts/{script_id}/refine")
    async def refine_script(
        script_id: str,
        req: ScriptRefineRequest,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        s = await db.scripts.find_one({"id": script_id, "client_id": client_id}, {"_id": 0})
        if not s:
            raise HTTPException(404, "Script not found")
        opp = await deps["get_opportunity"](s["opportunity_id"])
        creator = opp["creator"] if opp else {}
        style = creator.get("style", {})
        prompt = (
            f"Existing script:\n\n{s['body']}\n\n---\n\n"
            f"User instruction: {req.instruction}\n\n"
            f"Rewrite the FULL script applying the instruction. Keep the creator's voice "
            f"(tone: {style.get('tone','')}). Return only the new script text — no preamble, no explanation."
        )
        new_body = await deps["call_llm"](
            "You are a top-tier YouTube script editor. Return only the revised script text.",
            prompt, session_id=f"script-refine-{script_id}",
        )
        await db.scripts.update_one(
            {"id": script_id},
            {"$set": {"body": new_body, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        # Log turn
        await db.script_history.insert_one({
            "script_id": script_id, "instruction": req.instruction,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        return {"body": new_body}

    # ---------------- Weekly Calendar ----------------
    class PlanCreate(BaseModel):
        opportunity_id: str
        date: str  # YYYY-MM-DD
        notes: Optional[str] = None

    class PlanMove(BaseModel):
        date: str

    @router.get("/calendar")
    async def list_plan(
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        items = await db.calendar.find({"client_id": client_id}, {"_id": 0}).sort("date", 1).to_list(200)
        enriched = []
        for it in items:
            o = await deps["get_opportunity"](it["opportunity_id"])
            if o:
                enriched.append({**it, "opportunity": o})
        return enriched

    @router.post("/calendar")
    async def add_plan(
        req: PlanCreate,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        doc = {
            "id": str(uuid.uuid4()),
            "client_id": client_id,
            "opportunity_id": req.opportunity_id,
            "date": req.date,
            "notes": req.notes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.calendar.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.patch("/calendar/{plan_id}")
    async def move_plan(
        plan_id: str, req: PlanMove,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        r = await db.calendar.update_one({"id": plan_id, "client_id": client_id}, {"$set": {"date": req.date}})
        if r.matched_count == 0:
            raise HTTPException(404, "Plan not found")
        return {"ok": True}

    @router.delete("/calendar/{plan_id}")
    async def delete_plan(
        plan_id: str,
        x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
        sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
    ):
        client_id = cid(x_client_id, sid)
        await db.calendar.delete_one({"id": plan_id, "client_id": client_id})
        return {"ok": True}

    # ---------------- Real DNA (from connected YouTube) ----------------
    async def _derive_dna_from_channel(user: dict) -> Optional[dict]:
        """Use LLM to infer pillars/formats/style from video titles + subs."""
        ch = user.get("youtube_channel") or {}
        vids = user.get("recent_videos") or []
        if not ch or not vids:
            return None
        cached = await db.llm_cache.find_one({"kind": "user_dna", "key": user["id"]}, {"_id": 0})
        if cached:
            base = cached["value"]
        else:
            titles = "\n".join(f"- {v['title']} ({v.get('views',0):,} views)" for v in vids[:20])
            prompt = (
                f"Channel: {ch.get('title','')} ({ch.get('subscribers',0):,} subs). Description: {ch.get('description','')[:400]} "
                f"Recent videos with views:\n{titles}\n\n"
                "Infer this creator's DNA and return JSON: {"
                "\"niche\": \"1 phrase\", "
                "\"pillars\": [ {\"name\": \"...\", \"pct\": 0-100} for top 4-5 pillars, pct roughly sums to 100 ], "
                "\"formats\": [ {\"name\": \"...\", \"multiplier\": 0.6-2.5, \"label\": \"Best|Strong|Solid|Weak\"} for 3-5 formats ], "
                "\"style\": {\"tone\": \"...\", \"pace\": \"...\", \"hook_style\": \"...\", \"visual\": \"...\"}, "
                "\"audience_interests\": [ {\"name\": \"...\", \"affinity\": 0-100} for 3-5 ]}"
            )
            text = await deps["call_llm"](
                "You are a creator analyst. Return only valid JSON grounded in the observed titles.",
                prompt, session_id=f"user-dna-{user['id']}",
            )
            try:
                base = deps["extract_json"](text)
            except Exception:
                return None
            await db.llm_cache.update_one(
                {"kind": "user_dna", "key": user["id"]},
                {"$set": {"kind": "user_dna", "key": user["id"], "value": base,
                          "cached_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        return {
            "id": f"me-{user['id']}",
            "name": ch.get("title", user.get("name", "You")),
            "handle": ch.get("title", ""),
            "niche": base.get("niche", ""),
            "subscribers": ch.get("subscribers", 0),
            "avatar_gradient": ["#8A2BE2", "#4C1D95"],
            "initials": (ch.get("title", "?")[:1] or "?").upper(),
            "bio": ch.get("description", "")[:180],
            "pillars": base.get("pillars", []),
            "formats": base.get("formats", []),
            "style": base.get("style", {}),
            "audience_interests": base.get("audience_interests", []),
            "historical_videos": [
                {"title": v["title"], "format": "Video", "views": v.get("views", 0),
                 "grad": ["#8A2BE2", "#4C1D95"]}
                for v in (user.get("recent_videos") or [])[:20]
            ],
            "is_real": True,
        }

    @router.get("/me/creator")
    async def creator_me(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        user = await current_user(db, sid)
        if not user:
            raise HTTPException(401, "Not logged in")
        dna = await _derive_dna_from_channel(user)
        if not dna:
            raise HTTPException(404, "No YouTube channel data available for this account")
        return dna

    @router.get("/me/opportunities")
    async def opps_me(sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
        """Reflow scored opportunities using the user's own inferred DNA — formats & audience remap CreatorFit + FormatFit sub-scores."""
        user = await current_user(db, sid)
        if not user:
            raise HTTPException(401, "Not logged in")
        dna = await _derive_dna_from_channel(user)
        if not dna:
            raise HTTPException(404, "No DNA")
        best_mult = max((f.get("multiplier", 1) for f in dna.get("formats", [])), default=1)
        # Simple reflow: keep TrendFit/Freshness/Saturation from seed but recompute CreatorFit + FormatFit
        reflowed = []
        for o in deps["OPPORTUNITIES"]:
            trend = next((t for t in deps["TRENDS"] if t["id"] == o["trend_id"]), None)
            # Personalized creator fit: does this trend appear in user's pillars/interests?
            hay = " ".join([trend["name"] if trend else "",
                             " ".join(p["name"] for p in dna.get("pillars", [])),
                             " ".join(a["name"] for a in dna.get("audience_interests", []))]).lower()
            creator_fit = 60 + min(30, sum(20 for kw in (trend["name"].lower().split() if trend else []) if kw in hay))
            format_fit = int(min(100, 50 + best_mult * 20))
            sub = {**o["sub_scores"], "CreatorFit": creator_fit, "HistoricalFormatFit": format_fit}
            reflowed.append({**o, "sub_scores": sub, "score": deps["compute_opportunity_score"](sub), "trend": trend})
        return reflowed

    return router
