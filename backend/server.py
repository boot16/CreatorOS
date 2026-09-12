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
from api.m5 import build_m5_router
from api.workflow import build_workflow_router
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
_startup_issues = settings.validate_production()
if _startup_issues:
    for issue in _startup_issues:
        log.error(f"startup_config_issue: {issue}")

client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]
app = FastAPI(title="CreatorOS API")
cors_origins = settings.CORS_ORIGINS
if settings.is_production and "*" in cors_origins:
    log.error("CORS_ORIGINS='*' in production — refusing to enable credentials")
    cors_origins = [o for o in cors_origins if o != "*"]
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=cors_origins or ["*"], allow_methods=["*"], allow_headers=["*"])
MAX_JSON_BODY = 256 * 1024

@app.middleware("http")
async def context_middleware(request: Request, call_next):
    new_request_id()
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_JSON_BODY:
        return await app_error_handler(request, AppError(Codes.PAYLOAD_TOO_LARGE, f"Request body exceeds {MAX_JSON_BODY} bytes", status_code=413))
    return await call_next(request)

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
async def _identity(sid: Optional[str]): return await resolve_identity(db, sid)
def get_client_id(x_client_id: Optional[str], sid: Optional[str]) -> str: return sid or x_client_id or "demo-anonymous"

@api_router.get("/")
async def root(): return {"service": "CreatorOS", "data_mode": settings.DATA_MODE}

@api_router.get("/config")
async def config(): return {"data_mode": settings.DATA_MODE, "weights": {"opportunity": WEIGHTS_OPP, "compatibility": WEIGHTS_COMPAT}}

@api_router.get("/creators/{creator_id}")
async def creator(creator_id: str, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid); c = await make_creator_provider(db).get_creator(creator_id, user)
    if not c: raise AppError(Codes.NOT_FOUND, "Creator not found", status_code=404)
    return c

@api_router.get("/creators/{creator_id}/opportunities")
async def creator_opps(creator_id: str, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid); result = await make_opportunity_provider().list_for_creator(user)
    return result["items"] if isinstance(result, dict) and result.get("status") == "ready" else result

@api_router.get("/opportunities/{opp_id}")
async def opportunity_detail(opp_id: str, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid); o = await make_opportunity_provider().get(opp_id, user)
    if not o: raise AppError(Codes.NOT_FOUND, "Opportunity not found", status_code=404)
    return o

@api_router.get("/trends")
async def trends_list(category: Optional[str] = None): return await make_trend_provider().list_trends(category)

@api_router.get("/trends/{trend_id}")
async def trend_detail(trend_id: str):
    t = await make_trend_provider().get_trend(trend_id)
    if not t: raise AppError(Codes.NOT_FOUND, "Trend not found", status_code=404)
    return t

@api_router.get("/compatibility/{a}/{b}")
async def compatibility(a: str, b: str):
    if not settings.is_demo: raise AppError(Codes.NOT_COMPUTED, "Compatibility scoring not yet available", status_code=404)
    if {a, b} != {ALEX["id"], SARAH["id"]}: raise AppError(Codes.NOT_FOUND, "Compatibility not seeded for that pair", status_code=404)
    return {**COMPATIBILITY, "weights": WEIGHTS_COMPAT}

class IdeaRequest(BaseModel):
    opportunity_id: str
    regenerate: bool = False

@api_router.post("/idea-lab")
async def idea_lab(req: IdeaRequest, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE), x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")):
    user = await _identity(sid); rl_key = f"ideas-{user.user_id}" if user.is_authenticated else f"ideas-anon-{x_client_id or 'x'}"
    get_rate_limiter().check(rl_key, *BUDGETS["llm_idea_lab"])
    o = await make_opportunity_provider().get(req.opportunity_id, user)
    if not o: raise AppError(Codes.NOT_FOUND, "Opportunity not found", status_code=404)
    creator_ = o["creator"]; trend = o["trend"]
    prompt = f"Creator: {creator_['name']}. Trend: {trend['name']}. Working title: {o['title']}. Return JSON with concept, 4 titles, 3 hooks, 5 structure beats."
    result = await call_structured("You are a creator strategist. Return only JSON.", prompt, session_id=f"idea-{req.opportunity_id}", schema=IdeaLabOutput)
    return result.model_dump()

class ProposalRequest(BaseModel):
    from_creator_id: str
    to_creator_id: str
    message: str
    idea: Optional[str] = None

@api_router.post("/collab-proposal")
async def collab_proposal(req: ProposalRequest, sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE), x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")):
    user = await _identity(sid); from_id = user.creator_id or user.user_id if user.is_authenticated else req.from_creator_id
    await db.proposals.insert_one({"from_creator_id": from_id, "to_creator_id": req.to_creator_id, "message": req.message, "idea": req.idea, "created_at": datetime.now(timezone.utc).isoformat()})
    return {"status": "sent", "message": "Proposal recorded."}

class ShortlistItem(BaseModel):
    opportunity_id: str
    note: Optional[str] = None

def _owner_key(user, x_client_id): return f"user:{user.user_id}" if user.is_authenticated else f"browser:{x_client_id or 'demo-anonymous'}"

@api_router.get("/shortlist")
async def shortlist_get(x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"), sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid); return await db.shortlist.find({"owner_key": _owner_key(user, x_client_id)}, {"_id": 0}).sort("saved_at", -1).to_list(200)

@api_router.post("/shortlist")
async def shortlist_add(item: ShortlistItem, x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"), sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid); key = _owner_key(user, x_client_id)
    await db.shortlist.update_one({"owner_key": key, "opportunity_id": item.opportunity_id}, {"$set": {"owner_key": key, "opportunity_id": item.opportunity_id, "note": item.note, "saved_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"ok": True}

@api_router.delete("/shortlist/{opp_id}")
async def shortlist_remove(opp_id: str, x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"), sid: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    user = await _identity(sid); r = await db.shortlist.delete_one({"owner_key": _owner_key(user, x_client_id), "opportunity_id": opp_id}); return {"ok": True, "removed": r.deleted_count}

@api_router.get("/health")
async def health(): return {"status": "ok", "service": "CreatorOS", "data_mode": settings.DATA_MODE}

app.include_router(api_router)
app.include_router(build_auth_router(db), prefix="/api")
app.include_router(build_features_router(db, {
    "get_opportunity": lambda opp_id: make_opportunity_provider().get(opp_id, __import__("core.identity", fromlist=["CurrentUser"]).CurrentUser(user_id="feat", creator_id=DEMO_CREATOR_ID, workspace_id=None, is_authenticated=False, is_demo=settings.is_demo)),
    "get_creator_data": lambda cid: make_creator_provider(db).get_creator(cid, __import__("core.identity", fromlist=["CurrentUser"]).CurrentUser(user_id="feat", creator_id=DEMO_CREATOR_ID, workspace_id=None, is_authenticated=False, is_demo=settings.is_demo)),
    "call_llm": call_text,
    "extract_json": lambda text: __import__("json").loads(re.search(r"\{[\s\S]*\}", text).group(0)) if re.search(r"\{[\s\S]*\}", text) else (_ for _ in ()).throw(ValueError("No JSON")),
    "WEIGHTS_OPP": WEIGHTS_OPP, "OPPORTUNITIES": OPPORTUNITIES, "TRENDS": TRENDS,
    "compute_opportunity_score": compute_opportunity_score, "ALEX": ALEX,
}), prefix="/api")
app.include_router(build_v1_router(db), prefix="/api")
app.include_router(build_m5_router(db), prefix="/api")
app.include_router(build_workflow_router(db), prefix="/api")
log.info("routers_mounted")
