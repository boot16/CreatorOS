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

# Free-tier-friendly defaults for each provider, used when LLM_MODEL isn't set.
# Groq and Gemini both have real free tiers — good for testing without spend,
# but weaker output quality than Claude and their own rate limits (Groq's free
# tier is quite strict on requests/minute; Gemini's varies by model).
_DEFAULT_MODEL_FOR_PROVIDER = {
    "anthropic": "claude-sonnet-4-6",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
}


def _default_model_id() -> tuple:
    settings = get_settings()
    provider = settings.LLM_PROVIDER if settings.LLM_PROVIDER in _DEFAULT_MODEL_FOR_PROVIDER else "anthropic"
    model = settings.LLM_MODEL or _DEFAULT_MODEL_FOR_PROVIDER[provider]
    return (provider, model)


async def _call(system: str, user: str, session_id: str, model_id: tuple) -> str:
    """Call the configured LLM provider directly (no third-party wrapper).
    model_id is (provider, model) — provider is one of anthropic | groq | gemini."""
    provider, model = model_id
    try:
        settings = get_settings()
        if provider == "groq":
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            resp = await client.chat.completions.create(
                model=model, max_tokens=4096,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            return resp.choices[0].message.content or ""

        if provider == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            resp = await client.aio.models.generate_content(
                model=model, contents=user,
                config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=4096),
            )
            return resp.text or ""

        # default: anthropic
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=model, max_tokens=4096, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")
    except Exception as exc:
        log.exception(f"LLM upstream error session={session_id} provider={provider}")
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
    schema: Type[T], model_id: Optional[tuple] = None,
    max_retries: int = 1,
) -> T:
    model_id = model_id or _default_model_id()
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
                     model_id: Optional[tuple] = None) -> str:
    return await _call(system, user, session_id, model_id or _default_model_id())


class CachedLLMService:
    """Versioned cache wrapper. Cache is invalidated by bumping data_version or prompt_version."""
    def __init__(self, db):
        self.repo = LLMCacheRepo(db)

    async def get_or_compute(
        self, *, cache_kind: str, entity_id: str,
        entity_version: int = 1, data_version: int = 1, prompt_version: int = 1,
        model_id: Optional[tuple] = None,
        compute_fn,  # async callable returning JSON-serializable value
        bust: bool = False,
    ):
        model_id = model_id or _default_model_id()
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
