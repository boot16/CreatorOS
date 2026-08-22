from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import re
import uuid
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from core.config import get_settings
from core.errors import AppError, Codes, app_error_handler, http_exception_handler, validation_error_handler
from core.logging import configure_logging, get_logger, new_request_id
from core.identity import SESSION_COOKIE, resolve_identity, require_real_auth, require_creator, DEMO_CREATOR_ID
from core.rate_limit import get_rate_limiter, BUDGETS
from db.indexes import ensure_indexes
from providers import make_creator_provider, make_trend_provider, make_opportunity_provider
from services.llm import CachedLLMService, call_structured, call_text
from api.schemas import IdeaLabOutput, OppBulletsOutput, TrendExplanationOutput
from api.v1 import build_v1_router
from repositories import CreatorRepo

from seed_data import (
    ALEX, SARAH, COMPATIBILITY, TRENDS, OPPORTUNITIES,
    HISTORICAL_VIDEOS, WEIGHTS_OPP, WEIGHTS_COMPAT,
    compute_opportunity_score, compute_compatibility_score,
)
from auth_google import build_router as build_auth_router
from dna_card import render_dna_card
from features import build_router as build_features_router

configure_logging()
log = get_logger("server")

settings = get_settings()

# Startup validation
_startup_issues = settings.validate_production()
if _startup_issues:
    for issue in _startup_issues:
        log.error(f"startup_config_issue: {issue}")

client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]

app = FastAPI(title="CreatorOS API")

# CORS — production requires explicit origins; wildcard only for demo mode
cors_origins = settings.CORS_ORIGINS
if settings.is_production and "*" in cors_origins:
    log.error("CORS_ORIGINS='*' in production — refusing to enable credentials")
    cors_origins = [o for o in cors_origins if o != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request-ID + payload guard middleware
MAX_JSON_BODY = 256 * 1024  # 256 KB


@app.middleware("http")
async def context_middleware(request: Request, call_next):
    new_request_id()
    # Body-size guard for JSON writes (best-effort — full guard via Content-Length header)
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_JSON_BODY:
        return await app_error_handler(request, AppError(
            Codes.PAYLOAD_TOO_LARGE, f"Request body exceeds {MAX_JSON_BODY} bytes", status_code=413,
        ))
    response = await call_next(request)
    return response


# Error handlers — consistent shape
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)


@app.on_event("startup")
async def _startup():
    await ensure_indexes(db)
    log.info(f"startup data_mode={settings.DATA_MODE}")


@app.on_event("shutdown")
async def _shutdown():
    client.close()


api_router = APIRouter(prefix="/api")


# Helpers to resolve identity for legacy routes
async def _identity(sid: Optional[str]):
    return await resolve_identity(db, sid)


def get_client_id(x_client_id: Optional[str], sid: Optional[str]) -> str:
    return sid or x_client_id or "demo-anonymous"


# ---------- Root + config ----------
@api_router.get("/")
async def root():
    return {"service": "CreatorOS", "data_mode": settings.DATA_MODE}


@api_router.get("/config")
async def config():
    return {
        "data_mode": settings.DATA_MODE,
        "weights": {"opportunity": WEIGHTS_OPP, "compatibility": WEIGHTS_COMPAT},
    }


# ---------- Creators / Opportunities / Trends via providers ----------
@api_router.get("/creators/{creator_id}")
async def creator(creator_id: str, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid)
    prov = make_creator_provider(db)
    c = await prov.get_creator(creator_id, user)
    if not c:
        raise AppError(Codes.NOT_FOUND, "Creator not found", status_code=404)
    return c


@api_router.get("/creators/{creator_id}/opportunities")
async def creator_opps(creator_id: str, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid)
    prov = make_opportunity_provider()
    result = await prov.list_for_creator(user)
    # legacy frontend expects a bare list for the demo path
    if isinstance(result, dict) and result.get("status") == "ready":
        return result["items"]
    if isinstance(result, dict):
        return result
    return result


@api_router.get("/opportunities/{opp_id}")
async def opportunity_detail(opp_id: str, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid)
    prov = make_opportunity_provider()
    o = await prov.get(opp_id, user)
    if not o:
        if settings.is_production:
            raise AppError(Codes.NOT_COMPUTED, "Opportunity data is not yet available", status_code=404)
        raise AppError(Codes.NOT_FOUND, "Opportunity not found", status_code=404)

    # LLM: cached why bullets — versioned
    llm = CachedLLMService(db)
    async def compute():
        creator_ = o["creator"]; trend = o["trend"]
        prompt = (
            f"Creator: {creator_['name']} ({creator_['niche']}, {creator_['subscribers']:,} subs). "
            f"Best format: {creator_['formats'][0]['name']} ({creator_['formats'][0]['multiplier']}x). "
            f"Trend: {trend['name']} ({trend['stage']}, momentum {trend['momentum']}%). "
            f"Proposed video: '{o['title']}' as {o['format']}. "
            f"Reasoning seed: {o['why_bullets_seed']} "
            f"Return exactly 4 short bullets (max 18 words each). "
            f"Return JSON only: {{\"bullets\": [\"...\",\"...\",\"...\",\"...\"]}}"
        )
        result = await call_structured(
            "You are a creator strategist. Return only valid JSON.",
            prompt, session_id=f"opp-{opp_id}", schema=OppBulletsOutput,
        )
        return result.model_dump()["bullets"][:4]
    bullets = await llm.get_or_compute(
        cache_kind="opp_why", entity_id=opp_id, prompt_version=1, compute_fn=compute,
    )
    o["why_bullets"] = bullets
    return o


@api_router.get("/trends")
async def trends_list(category: Optional[str] = None):
    result = await make_trend_provider().list_trends(category)
    # legacy frontend expects a bare list in demo mode
    if isinstance(result, list):
        return result
    return result


@api_router.get("/trends/{trend_id}")
async def trend_detail(trend_id: str):
    prov = make_trend_provider()
    t = await prov.get_trend(trend_id)
    if not t:
        raise AppError(Codes.NOT_FOUND, "Trend not found", status_code=404)
    linked_opp = None
    if settings.is_demo:
        linked_opp = next((o for o in OPPORTUNITIES if o["trend_id"] == trend_id and o["creator_id"] == "alex-morgan"), None)

    llm = CachedLLMService(db)
    async def compute():
        prompt = (
            f"Trend: {t['name']} (category: {t['category']}, stage: {t['stage']}, "
            f"momentum: {t['momentum']}%, saturation: {t['saturation']}). "
            f"Return JSON: {{\"why\": \"2-sentence explanation\", "
            f"\"related\": [\"topic1\",\"topic2\",\"topic3\"], "
            f"\"audience\": \"1-sentence description of who's driving it\"}}"
        )
        result = await call_structured(
            "You are a media trend analyst. Return only valid JSON.",
            prompt, session_id=f"trend-{trend_id}", schema=TrendExplanationOutput,
        )
        return result.model_dump()
    explanation = await llm.get_or_compute(
        cache_kind="trend_why", entity_id=trend_id, prompt_version=1, compute_fn=compute,
    )
    return {**t, "explanation": explanation,
            "linked_opportunity_id": linked_opp["id"] if linked_opp else None}


@api_router.get("/compatibility/{a}/{b}")
async def compatibility(a: str, b: str):
    if not settings.is_demo:
        raise AppError(Codes.NOT_COMPUTED, "Compatibility scoring not yet available", status_code=404)
    if {a, b} != {ALEX["id"], SARAH["id"]}:
        raise AppError(Codes.NOT_FOUND, "Compatibility not seeded for that pair", status_code=404)
    return {**COMPATIBILITY, "weights": WEIGHTS_COMPAT}


# ---------- Idea Lab ----------
class IdeaRequest(BaseModel):
    opportunity_id: str
    regenerate: bool = False


@api_router.post("/idea-lab")
async def idea_lab(req: IdeaRequest,
                    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
                    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")):
    user = await _identity(sid)
    # Per-browser fallback in demo so one heavy user doesn't lock the whole demo
    rl_key = f"ideas-{user.user_id}" if user.is_authenticated else f"ideas-anon-{x_client_id or 'x'}"
    get_rate_limiter().check(rl_key, *BUDGETS["llm_idea_lab"])
    prov = make_opportunity_provider()
    o = await prov.get(req.opportunity_id, user)
    if not o:
        raise AppError(Codes.NOT_FOUND, "Opportunity not found", status_code=404)

    llm = CachedLLMService(db)
    async def compute():
        creator_ = o["creator"]; trend = o["trend"]
        nonce = uuid.uuid4().hex[:6] if req.regenerate else ""
        prompt = (
            f"Creator DNA: {creator_['name']}, {creator_['subscribers']:,} subs, niche {creator_['niche']}. "
            f"Best format: {creator_['formats'][0]['name']} ({creator_['formats'][0]['multiplier']}x baseline). "
            f"Style — tone: {creator_['style']['tone']}, hook: {creator_['style']['hook_style']}, pace: {creator_['style']['pace']}. "
            f"Trend: {trend['name']} ({trend['stage']}, +{trend['momentum']}% momentum). "
            f"Working title: '{o['title']}'. Format: {o['format']}. "
            + (f"Session {nonce} — deliver a fresh angle. " if nonce else "")
            + "Return JSON: {\"concept\": \"3-4 sentences\", "
              "\"titles\": [4 strings under 65 chars], "
              "\"hooks\": [3 opening lines], "
              "\"structure\": [5 beats]}"
        )
        result = await call_structured(
            "You are a top-tier YouTube script consultant. Return only valid JSON.",
            prompt, session_id=f"idea-{req.opportunity_id}", schema=IdeaLabOutput,
        )
        return result.model_dump()
    return await llm.get_or_compute(
        cache_kind="idea_lab", entity_id=req.opportunity_id,
        prompt_version=2, compute_fn=compute, bust=req.regenerate,
    )


# ---------- Proposal ----------
class ProposalRequest(BaseModel):
    from_creator_id: str
    to_creator_id: str
    message: str
    idea: Optional[str] = None


@api_router.post("/collab-proposal")
async def collab_proposal(req: ProposalRequest, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
                           x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")):
    user = await _identity(sid)
    # Rate limit — per user in prod, per browser in demo to avoid a single "demo-user" locking everyone out
    rl_key = f"collab-{user.user_id}" if user.is_authenticated else f"collab-anon-{x_client_id or 'x'}"
    get_rate_limiter().check(rl_key, *BUDGETS["collab_proposal"])
    if len(req.message) > 4000:
        raise AppError(Codes.PAYLOAD_TOO_LARGE, "Message too long", status_code=413)
    # Owner is ALWAYS the resolved caller identity — never trust body-supplied from_creator_id in production
    if user.is_authenticated:
        from_id = user.creator_id or user.user_id
    else:
        # demo/anonymous — allow body value only for backward-compat demo flow
        from_id = req.from_creator_id if user.is_demo else "anonymous"
    doc = {
        "from_creator_id": from_id,
        "to_creator_id": req.to_creator_id,
        "message": req.message,
        "idea": req.idea,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.proposals.insert_one(doc)
    return {"status": "sent", "message": "Proposal recorded."}


# ---------- Shortlist (per-user when authenticated, per-browser when demo) ----------
class ShortlistItem(BaseModel):
    opportunity_id: str
    note: Optional[str] = None


def _owner_key(user, x_client_id):
    """Owner key: real user ID when authenticated, else browser client ID."""
    if user.is_authenticated:
        return f"user:{user.user_id}"
    return f"browser:{x_client_id or 'demo-anonymous'}"


@api_router.get("/shortlist")
async def shortlist_get(
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    user = await _identity(sid)
    key = _owner_key(user, x_client_id)
    items = await db.shortlist.find({"owner_key": key}, {"_id": 0}).sort("saved_at", -1).to_list(200)
    prov = make_opportunity_provider()
    enriched = []
    for it in items:
        o = await prov.get(it["opportunity_id"], user)
        if o:
            enriched.append({**it, "opportunity": o})
    return enriched


@api_router.post("/shortlist")
async def shortlist_add(
    item: ShortlistItem,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    user = await _identity(sid)
    key = _owner_key(user, x_client_id)
    doc = {"owner_key": key, "opportunity_id": item.opportunity_id, "note": item.note,
           "saved_at": datetime.now(timezone.utc).isoformat()}
    await db.shortlist.update_one(
        {"owner_key": key, "opportunity_id": item.opportunity_id},
        {"$set": doc}, upsert=True,
    )
    return {"ok": True}


@api_router.delete("/shortlist/{opp_id}")
async def shortlist_remove(
    opp_id: str,
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
    sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    user = await _identity(sid)
    key = _owner_key(user, x_client_id)
    r = await db.shortlist.delete_one({"owner_key": key, "opportunity_id": opp_id})
    return {"ok": True, "removed": r.deleted_count}


# ---------- DNA card ----------
@api_router.get("/dna-card/{creator_id}.png")
async def dna_card(creator_id: str, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid)
    prov = make_creator_provider(db)
    c = await prov.get_creator(creator_id, user)
    if not c:
        raise AppError(Codes.NOT_FOUND, "Creator not found", status_code=404)
    # DNA card renderer expects full seeded shape — only supported in demo for now
    if not settings.is_demo:
        raise AppError(Codes.NOT_COMPUTED, "DNA card image not yet available for real creators", status_code=404)
    png = render_dna_card(c)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


# ---------- Assistant (rate limited) ----------
class AssistantMessage(BaseModel):
    role: str
    content: str


class AssistantRequest(BaseModel):
    session_id: str
    creator_id: str = DEMO_CREATOR_ID
    messages: List[AssistantMessage]


def _build_system(creator: dict) -> str:
    pillars = ", ".join(f"{p['name']} ({p['pct']}%)" for p in creator.get("pillars", []))
    formats = ", ".join(f"{f['name']} {f['multiplier']}x" for f in creator.get("formats", [])[:3])
    style = creator.get("style", {})
    return (
        f"You are the AI creative assistant inside CreatorOS Studio for {creator.get('name','')} "
        f"({creator.get('subscribers',0):,} subs, niche: {creator.get('niche','')}). "
        f"Pillars: {pillars}. Formats: {formats}. Tone: {style.get('tone','')}. "
        "Be a concise, opinionated creative partner. Under 200 words."
    )


@api_router.post("/assistant/chat")
async def assistant_chat(req: AssistantRequest,
                          sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
                          x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")):
    user = await _identity(sid)
    rl_key = f"chat-{user.user_id}" if user.is_authenticated else f"chat-anon-{x_client_id or 'x'}"
    get_rate_limiter().check(rl_key, *BUDGETS["llm_studio_chat"])
    # Payload guards
    if sum(len(m.content) for m in req.messages) > 30000:
        raise AppError(Codes.PAYLOAD_TOO_LARGE, "Chat context too large", status_code=413)

    prov = make_creator_provider(db)
    creator_ = await prov.get_current_creator(user) or await prov.get_creator(DEMO_CREATOR_ID, user) or ALEX
    system_msg = _build_system(creator_)

    convo = ""
    for m in req.messages[:-1]:
        convo += f"[{m.role.upper()}]: {m.content}\n"
    latest = req.messages[-1].content if req.messages else ""
    user_prompt = (convo + f"[USER]: {latest}\n[ASSISTANT]:").strip()

    await db.assistant_history.insert_one({
        "session_id": req.session_id, "role": "user", "content": latest,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async def gen():
        from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
        chat = LlmChat(api_key=settings.EMERGENT_LLM_KEY, session_id=f"studio-{req.session_id}",
                       system_message=system_msg).with_model("anthropic", "claude-sonnet-4-6")
        collected = ""
        async for ev in chat.stream_message(UserMessage(text=user_prompt)):
            if isinstance(ev, TextDelta):
                collected += ev.content
                yield ev.content
            elif isinstance(ev, StreamDone):
                break
        await db.assistant_history.insert_one({
            "session_id": req.session_id, "role": "assistant", "content": collected,
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


# ---------- Mount routers ----------
app.include_router(api_router)
app.include_router(build_auth_router(db), prefix="/api")
app.include_router(build_features_router(db, {
    "get_opportunity": lambda opp_id: make_opportunity_provider().get(opp_id, __import__("core.identity", fromlist=["CurrentUser"]).CurrentUser(
        user_id="feat", creator_id=DEMO_CREATOR_ID, workspace_id=None,
        is_authenticated=False, is_demo=settings.is_demo,
    )),
    "get_creator_data": lambda cid: make_creator_provider(db).get_creator(cid, __import__("core.identity", fromlist=["CurrentUser"]).CurrentUser(
        user_id="feat", creator_id=DEMO_CREATOR_ID, workspace_id=None,
        is_authenticated=False, is_demo=settings.is_demo,
    )),
    "call_llm": call_text,
    "extract_json": lambda text: __import__("json").loads(re.search(r"\{[\s\S]*\}", text).group(0)) if re.search(r"\{[\s\S]*\}", text) else (_ for _ in ()).throw(ValueError("No JSON")),
    "WEIGHTS_OPP": WEIGHTS_OPP,
    "OPPORTUNITIES": OPPORTUNITIES,
    "TRENDS": TRENDS,
    "compute_opportunity_score": compute_opportunity_score,
    "ALEX": ALEX,
}), prefix="/api")

app.include_router(build_v1_router(db), prefix="/api")

log.info("routers_mounted")
