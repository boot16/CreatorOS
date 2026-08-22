from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Header
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import logging
import re
import uuid
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from seed_data import (
    ALEX, SARAH, COMPATIBILITY, TRENDS, OPPORTUNITIES,
    HISTORICAL_VIDEOS, WEIGHTS_OPP, WEIGHTS_COMPAT,
    compute_opportunity_score, compute_compatibility_score,
)
from auth_google import build_router as build_auth_router, current_user, SESSION_COOKIE
from dna_card import render_dna_card
from features import build_router as build_features_router

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

DATA_MODE = os.environ.get("DATA_MODE", "demo")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

app = FastAPI(title="CreatorOS API")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ---------- Data-access seams ----------
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


# ---------- LLM ----------
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


async def bust_llm_cache(kind: str, key: str):
    await db.llm_cache.delete_one({"kind": kind, "key": key})


async def call_llm(system: str, user: str, session_id: str) -> str:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system,
        ).with_model("anthropic", "claude-sonnet-4-6")
        return await chat.send_message(UserMessage(text=user))
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")


async def stream_llm(system: str, user: str, session_id: str):
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")
    async for ev in chat.stream_message(UserMessage(text=user)):
        if isinstance(ev, TextDelta):
            yield ev.content
        elif isinstance(ev, StreamDone):
            break


def extract_json(text: str):
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON in LLM response")
    return json.loads(match.group(0))


# ---------- Client identity helper (no login required) ----------
def get_client_id(x_client_id: Optional[str], sid: Optional[str]) -> str:
    """Anonymous per-browser id (client sends stable UUID in X-Client-Id header) OR session id."""
    return sid or x_client_id or "demo-anonymous"


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"service": "CreatorOS", "data_mode": DATA_MODE}


@api_router.get("/config")
async def config():
    return {"data_mode": DATA_MODE, "weights": {"opportunity": WEIGHTS_OPP, "compatibility": WEIGHTS_COMPAT}}


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

    creator_ = o["creator"]; trend = o["trend"]
    prompt = (
        f"Creator: {creator_['name']} ({creator_['niche']}, {creator_['subscribers']:,} subs). "
        f"Best format: {creator_['formats'][0]['name']} ({creator_['formats'][0]['multiplier']}x). "
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
        bullets = extract_json(text).get("bullets", [])[:4]
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
            "why": f"{t['name']} is at the {t['stage']} stage with momentum {t['momentum']}%.",
            "related": [], "audience": "Early-adopter builders.",
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
    regenerate: bool = False


@api_router.post("/idea-lab")
async def idea_lab(req: IdeaRequest):
    o = await get_opportunity(req.opportunity_id)
    if not o:
        raise HTTPException(404, "Opportunity not found")

    cache_key = req.opportunity_id
    if req.regenerate:
        await bust_llm_cache("idea_lab", cache_key)
    else:
        cached = await get_cached_llm("idea_lab", cache_key)
        if cached:
            return cached

    creator_ = o["creator"]; trend = o["trend"]
    # add nonce so regen actually differs
    nonce = uuid.uuid4().hex[:6] if req.regenerate else ""
    prompt = (
        f"Creator DNA: {creator_['name']}, {creator_['subscribers']:,} subs, niche {creator_['niche']}. "
        f"Best format: {creator_['formats'][0]['name']} ({creator_['formats'][0]['multiplier']}x baseline). "
        f"Style — tone: {creator_['style']['tone']}, hook: {creator_['style']['hook_style']}, pace: {creator_['style']['pace']}. "
        f"Trend: {trend['name']} ({trend['stage']}, +{trend['momentum']}% momentum). "
        f"Working title: '{o['title']}'. Format: {o['format']}. "
        + (f"Session {nonce} — deliver a fresh angle different from any prior version. " if nonce else "")
        + f"Return JSON: {{"
          f"\"concept\": \"3-4 sentences describing the specific video concept, angle, and payoff\", "
          f"\"titles\": [4 strings each under 65 chars matching creator's voice], "
          f"\"hooks\": [3 short opening hook sentences for first 3s], "
          f"\"structure\": [5 strings, one per beat]}}"
    )
    text = await call_llm(
        "You are a top-tier YouTube script consultant. Return only valid JSON. Match the creator's voice exactly.",
        prompt, session_id=f"idea-{cache_key}-{nonce}",
    )
    try:
        result = extract_json(text)
    except Exception as e:
        raise HTTPException(502, f"Could not parse LLM output: {e}") from e
    else:
        await set_cached_llm("idea_lab", cache_key, result)
        return result


class ProposalRequest(BaseModel):
    from_creator_id: str
    to_creator_id: str
    message: str
    idea: Optional[str] = None


@api_router.post("/collab-proposal")
async def collab_proposal(req: ProposalRequest):
    doc = req.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.proposals.insert_one(doc)
    return {"status": "sent", "message": "Proposal recorded (demo mode — no real message sent)."}


# ---------- Shortlist (per-client, no login required) ----------
class ShortlistItem(BaseModel):
    opportunity_id: str
    note: Optional[str] = None


@api_router.get("/shortlist")
async def shortlist_get(
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    cid = get_client_id(x_client_id, sid)
    items = await db.shortlist.find({"client_id": cid}, {"_id": 0}).sort("saved_at", -1).to_list(200)
    # Attach opportunity payload
    enriched = []
    for it in items:
        o = await get_opportunity(it["opportunity_id"])
        if o:
            enriched.append({**it, "opportunity": o})
    return enriched


@api_router.post("/shortlist")
async def shortlist_add(
    item: ShortlistItem,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    cid = get_client_id(x_client_id, sid)
    doc = {
        "client_id": cid,
        "opportunity_id": item.opportunity_id,
        "note": item.note,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.shortlist.update_one(
        {"client_id": cid, "opportunity_id": item.opportunity_id},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True}


@api_router.delete("/shortlist/{opp_id}")
async def shortlist_remove(
    opp_id: str,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    cid = get_client_id(x_client_id, sid)
    r = await db.shortlist.delete_one({"client_id": cid, "opportunity_id": opp_id})
    return {"ok": True, "removed": r.deleted_count}


# ---------- DNA card PNG ----------
@api_router.get("/dna-card/{creator_id}.png")
async def dna_card(creator_id: str):
    c = await get_creator_data(creator_id)
    if not c:
        raise HTTPException(404, "Creator not found")
    png = render_dna_card(c)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


# ---------- AI Assistant (Studio) ----------
class AssistantMessage(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class AssistantRequest(BaseModel):
    session_id: str
    creator_id: str = "alex-morgan"
    messages: List[AssistantMessage]


def build_system_prompt(creator: dict) -> str:
    pillars = ", ".join(f"{p['name']} ({p['pct']}%)" for p in creator["pillars"])
    formats = ", ".join(f"{f['name']} {f['multiplier']}x" for f in creator["formats"][:3])
    return (
        f"You are the AI creative assistant inside CreatorOS Studio for {creator['name']} "
        f"({creator['subscribers']:,} subs, niche: {creator['niche']}). "
        f"Their pillars: {pillars}. Their format performance: {formats}. "
        f"Voice: {creator['style']['tone']}. Hook style: {creator['style']['hook_style']}. "
        "Be a concise, opinionated creative partner. Reference their DNA when relevant. "
        "Help them plan videos, brainstorm titles/hooks, draft scripts, react to ideas, "
        "and think through their week. Never be generic. Keep responses under 200 words unless asked."
    )


@api_router.post("/assistant/chat")
async def assistant_chat(req: AssistantRequest):
    creator_ = await get_creator_data(req.creator_id) or ALEX
    system = build_system_prompt(creator_)
    # Concatenate history into a single user turn for simplicity
    convo = ""
    for m in req.messages[:-1]:
        convo += f"[{m.role.upper()}]: {m.content}\n"
    latest = req.messages[-1].content if req.messages else ""
    user_prompt = (convo + f"[USER]: {latest}\n[ASSISTANT]:").strip()

    # Persist message
    await db.assistant_history.insert_one({
        "session_id": req.session_id,
        "role": "user", "content": latest,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async def gen():
        collected = ""
        async for chunk in stream_llm(system, user_prompt, session_id=f"studio-{req.session_id}"):
            collected += chunk
            yield chunk
        await db.assistant_history.insert_one({
            "session_id": req.session_id,
            "role": "assistant", "content": collected,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return StreamingResponse(gen(), media_type="text/plain",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api_router.get("/assistant/history/{session_id}")
async def assistant_history(session_id: str):
    items = await db.assistant_history.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    return items


# Mount routers
app.include_router(api_router)
app.include_router(build_auth_router(db), prefix="/api")
app.include_router(build_features_router(db, {
    "get_opportunity": get_opportunity,
    "get_creator_data": get_creator_data,
    "call_llm": call_llm,
    "extract_json": extract_json,
    "WEIGHTS_OPP": WEIGHTS_OPP,
    "OPPORTUNITIES": OPPORTUNITIES,
    "TRENDS": TRENDS,
    "compute_opportunity_score": compute_opportunity_score,
    "ALEX": ALEX,
}), prefix="/api")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
