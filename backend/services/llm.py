"""Provider-neutral LLM boundary for CreatorOS.

Application code calls only this module. Providers return text and safe usage
metadata; structured validation, repair, cache identity, and error translation
remain stable regardless of the provider selected later.
"""
import asyncio
import json
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import AsyncIterator, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

from core.config import get_settings
from core.errors import AppError, Codes
from core.logging import get_logger
from models.domain import LLMCacheEntry
from repositories import LLMCacheRepo

log = get_logger("services.llm")
T = TypeVar("T", bound=BaseModel)
DEFAULT_MAX_TOKENS = 4096


class LLMUnavailableError(AppError):
    def __init__(self, message: str = "AI service temporarily unavailable"):
        super().__init__(Codes.UPSTREAM_ERROR, message, status_code=502)


class LLMTimeoutError(AppError):
    def __init__(self):
        super().__init__(Codes.UPSTREAM_ERROR, "AI service timed out; please retry", status_code=504)


class LLMInvalidResponseError(AppError):
    def __init__(self, message: str = "AI returned an invalid structured response"):
        super().__init__(Codes.LLM_PARSE_ERROR, message, status_code=502)


@dataclass(frozen=True)
class LLMUsage:
    provider: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[int] = None


@dataclass(frozen=True)
class LLMCompletion:
    text: str
    usage: LLMUsage


class LLMProvider(Protocol):
    name: str
    async def complete(self, *, system: str, user: str, model: str,
                       max_tokens: int = DEFAULT_MAX_TOKENS) -> LLMCompletion: ...
    async def stream(self, *, system: str, user: str, model: str,
                     max_tokens: int = DEFAULT_MAX_TOKENS) -> AsyncIterator[str]: ...


class AnthropicProvider:
    """Official Anthropic async SDK adapter, isolated from application features."""
    name = "anthropic"

    def __init__(self, api_key: str, timeout_seconds: float, max_retries: int):
        if not api_key:
            raise LLMUnavailableError("AI service is not configured")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise LLMUnavailableError("AI provider package is not installed") from exc
        self.client = AsyncAnthropic(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)

    @staticmethod
    def _text(message) -> str:
        return "".join(getattr(block, "text", "") for block in getattr(message, "content", [])).strip()

    @staticmethod
    def _usage(message, model: str, started: float) -> LLMUsage:
        usage = getattr(message, "usage", None)
        return LLMUsage("anthropic", getattr(message, "model", model),
                        getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None),
                        round((time.monotonic() - started) * 1000))

    @staticmethod
    def _translate(exc: Exception) -> AppError:
        try:
            import anthropic
            if isinstance(exc, (anthropic.APITimeoutError, TimeoutError, asyncio.TimeoutError)):
                return LLMTimeoutError()
            if isinstance(exc, (anthropic.RateLimitError, anthropic.InternalServerError,
                                anthropic.APIConnectionError, anthropic.APIStatusError)):
                return LLMUnavailableError()
        except ImportError:
            pass
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return LLMTimeoutError()
        return LLMUnavailableError()

    async def complete(self, *, system: str, user: str, model: str,
                       max_tokens: int = DEFAULT_MAX_TOKENS) -> LLMCompletion:
        started = time.monotonic()
        try:
            message = await self.client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            raise self._translate(exc) from exc
        text = self._text(message)
        if not text:
            raise LLMInvalidResponseError("AI returned an empty response")
        return LLMCompletion(text, self._usage(message, model, started))

    async def stream(self, *, system: str, user: str, model: str,
                     max_tokens: int = DEFAULT_MAX_TOKENS) -> AsyncIterator[str]:
        started = time.monotonic()
        try:
            async with self.client.messages.stream(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                async for chunk in stream.text_stream:
                    if chunk:
                        yield chunk
                final = await stream.get_final_message()
                usage = self._usage(final, model, started)
                log.info("llm_stream_complete provider=%s model=%s input_tokens=%s output_tokens=%s duration_ms=%s",
                         usage.provider, usage.model, usage.input_tokens, usage.output_tokens, usage.duration_ms)
        except AppError:
            raise
        except Exception as exc:
            raise self._translate(exc) from exc


class LLMService:
    def __init__(self, provider: LLMProvider): self.provider = provider

    async def complete(self, *, system: str, user: str, session_id: str, model: str,
                       max_tokens: int = DEFAULT_MAX_TOKENS) -> LLMCompletion:
        try:
            result = await self.provider.complete(system=system, user=user, model=model, max_tokens=max_tokens)
        except AppError:
            raise
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise LLMTimeoutError() from exc
        except Exception as exc:
            raise LLMUnavailableError() from exc
        usage = result.usage
        log.info("llm_complete provider=%s model=%s input_tokens=%s output_tokens=%s duration_ms=%s session=%s",
                 usage.provider, usage.model, usage.input_tokens, usage.output_tokens, usage.duration_ms, session_id)
        return result

    async def stream(self, *, system: str, user: str, session_id: str, model: str,
                     max_tokens: int = DEFAULT_MAX_TOKENS) -> AsyncIterator[str]:
        try:
            async for chunk in self.provider.stream(system=system, user=user, model=model, max_tokens=max_tokens):
                yield chunk
        except AppError:
            raise
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise LLMTimeoutError() from exc
        except Exception as exc:
            raise LLMUnavailableError() from exc


def _resolve_model(model_id: Optional[tuple[str, str]]) -> tuple[str, str]:
    settings = get_settings()
    provider, model = model_id or (settings.LLM_PROVIDER, settings.LLM_MODEL)
    if provider != "anthropic":
        raise LLMUnavailableError("Configured AI provider is not supported")
    return provider, model


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    settings = get_settings()
    if settings.LLM_PROVIDER != "anthropic":
        raise LLMUnavailableError("Configured AI provider is not supported")
    return LLMService(AnthropicProvider(settings.ANTHROPIC_API_KEY, settings.LLM_TIMEOUT_SECONDS,
                                        settings.LLM_MAX_RETRIES))


def reset_llm_service() -> None:
    """Test hook after changing environment or injecting a replacement provider."""
    get_llm_service.cache_clear()


async def _call_completion(system: str, user: str, session_id: str, model_id: Optional[tuple[str, str]],
                           service: Optional[LLMService] = None) -> LLMCompletion:
    _provider, model = _resolve_model(model_id)
    return await (service or get_llm_service()).complete(system=system, user=user, session_id=session_id, model=model)


def _parse_json_object(text: str) -> dict:
    """Accept only an entire JSON object, optionally in one fenced JSON block."""
    candidate = text.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[len("```json"):-3].strip()
    elif candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMInvalidResponseError() from exc
    if not isinstance(parsed, dict):
        raise LLMInvalidResponseError("AI returned JSON of the wrong shape")
    return parsed


def parse_json_object(text: str) -> dict:
    """Compatibility parser for legacy callers; strict and provider-independent."""
    return _parse_json_object(text)


async def call_structured(system: str, user: str, session_id: str, schema: Type[T],
                          model_id: Optional[tuple[str, str]] = None, max_retries: int = 1,
                          service: Optional[LLMService] = None) -> T:
    """Strict JSON -> Pydantic flow with a bounded repair attempt."""
    text = (await _call_completion(system, user, session_id, model_id, service)).text
    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return schema.model_validate(_parse_json_object(text))
        except (LLMInvalidResponseError, ValidationError) as exc:
            last_error = exc
            if attempt == max_retries:
                break
            repair = ("Your previous response did not validate. Return only one valid JSON object matching this schema. "
                      f"Schema: {schema.model_json_schema()}\n\nOriginal request:\n{user}")
            text = (await _call_completion(system, repair, f"{session_id}-repair", model_id, service)).text
    raise LLMInvalidResponseError("AI response did not match the required schema") from last_error


async def call_text(system: str, user: str, session_id: str, model_id: Optional[tuple[str, str]] = None,
                    service: Optional[LLMService] = None) -> str:
    return (await _call_completion(system, user, session_id, model_id, service)).text


async def stream_text(system: str, user: str, session_id: str, model_id: Optional[tuple[str, str]] = None,
                      service: Optional[LLMService] = None) -> AsyncIterator[str]:
    _provider, model = _resolve_model(model_id)
    async for chunk in (service or get_llm_service()).stream(system=system, user=user, session_id=session_id, model=model):
        yield chunk


class CachedLLMService:
    """Versioned cache wrapper; configured model is part of every cache identity."""
    def __init__(self, db): self.repo = LLMCacheRepo(db)

    async def get_or_compute(self, *, cache_kind: str, entity_id: str, entity_version: int = 1,
                             data_version: int = 1, prompt_version: int = 1,
                             model_id: Optional[tuple[str, str]] = None, compute_fn=None, bust: bool = False):
        provider, model = _resolve_model(model_id)
        model_str = f"{provider}/{model}"
        key = self.repo.compute_key(cache_kind, entity_id, entity_version, data_version, prompt_version, model_str)
        if bust:
            await self.repo.bust(cache_kind, entity_id)
        else:
            cached = await self.repo.get(key)
            if cached is not None:
                return cached
        value = await compute_fn()
        await self.repo.put(LLMCacheEntry(cache_kind=cache_kind, entity_id=entity_id,
            entity_version=entity_version, data_version=data_version, prompt_version=prompt_version,
            model=model_str, key_hash=key, value=value))
        return value
