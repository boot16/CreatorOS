"""LLM service: structured JSON responses via Pydantic validation + versioned cache.

Never returns raw provider errors to clients.
"""
import json
import re
from typing import Type, TypeVar, Optional
from pydantic import BaseModel, ValidationError

from core.config import get_settings
from core.errors import AppError, Codes
from core.logging import get_logger
from models.domain import LLMCacheEntry
from repositories import LLMCacheRepo

log = get_logger("services.llm")

T = TypeVar("T", bound=BaseModel)


async def _call(system: str, user: str, session_id: str, model_id: tuple) -> str:
    """Call LLM via emergentintegrations. model_id is (provider, model)."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=get_settings().EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system,
        ).with_model(model_id[0], model_id[1])
        return await chat.send_message(UserMessage(text=user))
    except Exception as exc:
        log.exception(f"LLM upstream error session={session_id}")
        raise AppError(Codes.UPSTREAM_ERROR, "AI service temporarily unavailable", status_code=502) from exc


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise AppError(Codes.LLM_PARSE_ERROR, "AI returned invalid response", status_code=502)
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AppError(Codes.LLM_PARSE_ERROR, "AI returned malformed JSON", status_code=502) from exc


async def call_structured(
    system: str, user: str, session_id: str,
    schema: Type[T], model_id: tuple = ("anthropic", "claude-sonnet-4-6"),
    max_retries: int = 1,
) -> T:
    text = await _call(system, user, session_id, model_id)
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            data = _extract_json(text)
            return schema.model_validate(data)
        except (AppError, ValidationError) as exc:
            last_exc = exc
            if attempt < max_retries:
                # one repair attempt: ask model to fix
                repair_prompt = (
                    f"Your previous response could not be parsed. "
                    f"Return ONLY valid JSON matching this schema:\n{schema.model_json_schema()}\n\n"
                    f"Original request:\n{user}"
                )
                text = await _call(system, repair_prompt, session_id + "-repair", model_id)
    if isinstance(last_exc, AppError):
        raise last_exc
    raise AppError(Codes.LLM_PARSE_ERROR, "AI response did not match required schema", status_code=502)


async def call_text(system: str, user: str, session_id: str,
                     model_id: tuple = ("anthropic", "claude-sonnet-4-6")) -> str:
    return await _call(system, user, session_id, model_id)


class CachedLLMService:
    """Versioned cache wrapper. Cache is invalidated by bumping data_version or prompt_version."""
    def __init__(self, db):
        self.repo = LLMCacheRepo(db)

    async def get_or_compute(
        self, *, cache_kind: str, entity_id: str,
        entity_version: int = 1, data_version: int = 1, prompt_version: int = 1,
        model_id: tuple = ("anthropic", "claude-sonnet-4-6"),
        compute_fn,  # async callable returning JSON-serializable value
        bust: bool = False,
    ):
        model_str = f"{model_id[0]}/{model_id[1]}"
        key = self.repo.compute_key(cache_kind, entity_id, entity_version, data_version, prompt_version, model_str)
        if bust:
            await self.repo.bust(cache_kind, entity_id)
        else:
            cached = await self.repo.get(key)
            if cached is not None:
                return cached
        value = await compute_fn()
        entry = LLMCacheEntry(
            cache_kind=cache_kind, entity_id=entity_id, entity_version=entity_version,
            data_version=data_version, prompt_version=prompt_version, model=model_str,
            key_hash=key, value=value,
        )
        await self.repo.put(entry)
        return value
