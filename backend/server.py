from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import logging
import re
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from seed_data import (
    ALEX, SARAH, COMPATIBILITY, TRENDS, OPPORTUNITIES,
    HISTORICAL_VIDEOS, WEIGHTS_OPP, WEIGHTS_COMPAT,
    compute_opportunity_score, compute_compatibility_score,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

DATA_MODE = os.environ.get("DATA_MODE", "demo")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

app = FastAPI(title="CreatorOS API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ---------- Data-access seams (swap for real API later) ----------
async def get_creator_data(creator_id: str):
    if creator_id == ALEX["id"]:
        return ALEX
    if creator_id == SARAH["id"]:
        return SARAH
    return None


async def get_trends(category: Optional[str] = None):
    if category and category.lower() != "all":
        return [t for t in TRENDS if t["category"].lower() == category.lower()]
    return TRENDS


async def get_trend(trend_id: str):
    return next((t for t in TRENDS if t["id"] == trend_id), None)


async def get_opportunities(creator_id: str):
    items = [o for o in OPPORTUNITIES if o["creator_id"] == creator_id]
    return [
        {**o, "score": compute_opportunity_score(o["sub_scores"]),
         "trend": next((t for t in TRENDS if t["id"] == o["trend_id"]), None)}
        for o in items
    ]


async def get_opportunity(opp_id: str):
    o = next((x for x in OPPORTUNITIES if x["id"] == opp_id), None)
    if not o:
        return None
    return {**o, "score": compute_opportunity_score(o["sub_scores"]),
            "trend": next((t for t in TRENDS if t["id"] == o["trend_id"]), None),
            "creator": await get_creator_data(o["creator_id"])}


# ---------- LLM cached helpers ----------
async def get_cached_llm(kind: str, key: str):
    doc = await db.llm_cache.find_one({"kind": kind, "key": key}, {"_id": 0})
    return doc["value"] if doc else None


async def set_cached_llm(kind: str, key: str, value):
    await db.llm_cache.update_one(
        {"kind": kind, "key": key},
        {"$set": {"kind": kind, "key": key, "value": value,
                   "cached_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


async def call_llm(system: str, user: str, session_id: str) -> str:
    """Non-streaming call to Claude Sonnet 4.6 via emergentintegrations."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system,
        ).with_model("anthropic", "claude-sonnet-4-6")
        response = await chat.send_message(UserMessage(text=user))
        return response
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")


def extract_json(text: str):
    """Extract first JSON object from LLM text."""
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON in LLM response")
    return json.loads(match.group(0))


# ---------- Routes ----------
class ProposalRequest(BaseModel):
    from_creator_id: str
    to_creator_id: str
    message: str
    idea: Optional[str] = None


@api_router.get("/")
async def root():
    return {"service": "CreatorOS", "data_mode": DATA_MODE}


@api_router.get("/config")
async def config():
    return {
        "data_mode": DATA_MODE,
        "weights": {"opportunity": WEIGHTS_OPP, "compatibility": WEIGHTS_COMPAT},
    }


@api_router.get("/creators/{creator_id}")
async def creator(creator_id: str):
    c = await get_creator_data(creator_id)
    if not c:
        raise HTTPException(404, "Creator not found")
    if creator_id == ALEX["id"]:
        return {**c, "historical_videos": HISTORICAL_VIDEOS}
    return c


@api_router.get("/creators/{creator_id}/opportunities")
async def creator_opportunities(creator_id: str):
    return await get_opportunities(creator_id)


@api_router.get("/opportunities/{opp_id}")
async def opportunity_detail(opp_id: str):
    o = await get_opportunity(opp_id)
    if not o:
        raise HTTPException(404, "Opportunity not found")

    cached = await get_cached_llm("opp_why", opp_id)
    if cached:
        o["why_bullets"] = cached
        return o

    creator = o["creator"]
    trend = o["trend"]
    prompt = (
        f"Creator: {creator['name']} ({creator['niche']}, {creator['subscribers']:,} subs). "
        f"Best format: {creator['formats'][0]['name']} ({creator['formats'][0]['multiplier']}x). "
        f"Trend: {trend['name']} ({trend['stage']}, momentum {trend['momentum']}%). "
        f"Proposed video: '{o['title']}' as {o['format']}. "
        f"Reasoning seed: {o['why_bullets_seed']} "
        f"Return exactly 4 short bullets (max 18 words each) explaining why this specific opportunity fits this creator right now. "
        f"Return JSON only: {{\"bullets\": [\"...\",\"...\",\"...\",\"...\"]}}"
    )
    text = await call_llm(
        "You are a creator strategist. Return only valid JSON. Be concrete and reference the numbers.",
        prompt, session_id=f"opp-{opp_id}",
    )
    try:
        parsed = extract_json(text)
        bullets = parsed.get("bullets", [])[:4]
    except Exception:
        bullets = [b.strip() for b in o["why_bullets_seed"].split(".") if b.strip()][:4]
    await set_cached_llm("opp_why", opp_id, bullets)
    o["why_bullets"] = bullets
    return o


@api_router.get("/trends")
async def trends_list(category: Optional[str] = None):
    return await get_trends(category)


@api_router.get("/trends/{trend_id}")
async def trend_detail(trend_id: str):
    t = await get_trend(trend_id)
    if not t:
        raise HTTPException(404, "Trend not found")

    # tie back to Alex's opportunity if any
    linked_opp = next((o for o in OPPORTUNITIES if o["trend_id"] == trend_id and o["creator_id"] == ALEX["id"]), None)

    cached = await get_cached_llm("trend_why", trend_id)
    if cached:
        return {**t, "explanation": cached, "linked_opportunity_id": linked_opp["id"] if linked_opp else None}

    prompt = (
        f"Trend: {t['name']} (category: {t['category']}, stage: {t['stage']}, momentum: {t['momentum']}%, saturation: {t['saturation']}). "
        f"Return JSON: {{\"why\": \"2-sentence explanation of why this trend is rising now\", "
        f"\"related\": [\"topic1\",\"topic2\",\"topic3\"], "
        f"\"audience\": \"1-sentence description of who's driving it\"}}"
    )
    text = await call_llm(
        "You are a media trend analyst. Return only valid JSON. Be specific, no fluff.",
        prompt, session_id=f"trend-{trend_id}",
    )
    try:
        explanation = extract_json(text)
    except Exception:
        explanation = {
            "why": f"{t['name']} is at the {t['stage']} stage with momentum {t['momentum']}%. Search and creator interest have accelerated across niches.",
            "related": ["adjacent topic 1", "adjacent topic 2", "adjacent topic 3"],
            "audience": "Early-adopter builders, indie founders, and technical operators.",
        }
    await set_cached_llm("trend_why", trend_id, explanation)
    return {**t, "explanation": explanation, "linked_opportunity_id": linked_opp["id"] if linked_opp else None}


@api_router.get("/compatibility/{a}/{b}")
async def compatibility(a: str, b: str):
    if {a, b} != {ALEX["id"], SARAH["id"]}:
        raise HTTPException(404, "Compatibility not seeded for that pair")
    return {**COMPATIBILITY, "weights": WEIGHTS_COMPAT}


class IdeaRequest(BaseModel):
    opportunity_id: str


@api_router.post("/idea-lab")
async def idea_lab(req: IdeaRequest):
    o = await get_opportunity(req.opportunity_id)
    if not o:
        raise HTTPException(404, "Opportunity not found")

    cached = await get_cached_llm("idea_lab", req.opportunity_id)
    if cached:
        return cached

    creator = o["creator"]
    trend = o["trend"]
    prompt = (
        f"Creator DNA: {creator['name']}, {creator['subscribers']:,} subs, niche {creator['niche']}. "
        f"Best format: {creator['formats'][0]['name']} ({creator['formats'][0]['multiplier']}x baseline). "
        f"Style — tone: {creator['style']['tone']}, hook: {creator['style']['hook_style']}, pace: {creator['style']['pace']}. "
        f"Trend: {trend['name']} ({trend['stage']}, +{trend['momentum']}% momentum). "
        f"Working title: '{o['title']}'. Format: {o['format']}. "
        f"Return JSON: {{"
        f"\"concept\": \"3-4 sentences describing the specific video concept, angle, and payoff\", "
        f"\"titles\": [\"title 1\", \"title 2\", \"title 3\", \"title 4\"] (each under 65 chars, no clickbait, matching creator's voice), "
        f"\"hooks\": [\"opening hook 1\", \"opening hook 2\", \"opening hook 3\"] (each 1 short sentence for first 3s of video), "
        f"\"structure\": [\"beat 1\", \"beat 2\", \"beat 3\", \"beat 4\", \"beat 5\"] (video structure, 5 beats)"
        f"}}"
    )
    text = await call_llm(
        "You are a top-tier YouTube script consultant. Return only valid JSON. Match the creator's voice exactly.",
        prompt, session_id=f"idea-{req.opportunity_id}",
    )
    try:
        result = extract_json(text)
    except Exception as e:
        raise HTTPException(502, f"Could not parse LLM output: {e}")

    await set_cached_llm("idea_lab", req.opportunity_id, result)
    return result


@api_router.post("/collab-proposal")
async def collab_proposal(req: ProposalRequest):
    doc = req.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.proposals.insert_one(doc)
    return {"status": "sent", "message": "Proposal recorded (demo mode — no real message sent)."}


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
