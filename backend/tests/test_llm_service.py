"""LLM-port unit tests: all providers are mocked; no network or billing required."""
import os
import sys

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_llm")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("LLM_PROVIDER", "anthropic")
os.environ.setdefault("LLM_MODEL", "claude-sonnet-4-6")
sys.path.insert(0, "/app/backend")

import pytest
from pydantic import BaseModel

from services.llm import (
    LLMCompletion, LLMInvalidResponseError, LLMService, LLMTimeoutError,
    LLMUnavailableError, LLMUsage, call_structured, call_text, stream_text,
)


class Output(BaseModel):
    title: str


class FakeProvider:
    name = "fake"
    def __init__(self, responses=None, chunks=None, error=None):
        self.responses = list(responses or [])
        self.chunks = list(chunks or [])
        self.error = error
        self.calls = 0

    async def complete(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return LLMCompletion(self.responses.pop(0), LLMUsage("fake", "fake-model", 3, 2, 1))

    async def stream(self, **_kwargs):
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


@pytest.mark.asyncio
async def test_standard_completion_and_usage_metadata():
    provider = FakeProvider(responses=["hello"])
    assert await call_text("s", "u", "test", service=LLMService(provider)) == "hello"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_timeout_and_provider_failure_are_safe_errors():
    with pytest.raises(LLMTimeoutError):
        await call_text("s", "u", "test", service=LLMService(FakeProvider(error=TimeoutError())))
    with pytest.raises(LLMUnavailableError):
        await call_text("s", "u", "test", service=LLMService(FakeProvider(error=RuntimeError("upstream details"))))


@pytest.mark.asyncio
async def test_structured_valid_json_and_bounded_repair():
    provider = FakeProvider(responses=["not json", '{"title":"valid"}'])
    output = await call_structured("s", "u", "test", Output, service=LLMService(provider))
    assert output.title == "valid"
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_structured_schema_failure_and_exhausted_retry_are_safe():
    provider = FakeProvider(responses=['{"wrong":"shape"}', '{"still":"wrong"}'])
    with pytest.raises(LLMInvalidResponseError):
        await call_structured("s", "u", "test", Output, service=LLMService(provider), max_retries=1)
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_streaming_order_completion_and_midstream_failure():
    service = LLMService(FakeProvider(chunks=["one", " two", " three"]))
    assert [chunk async for chunk in stream_text("s", "u", "test", service=service)] == ["one", " two", " three"]
    failing = LLMService(FakeProvider(chunks=["one", RuntimeError("provider failure")]))
    stream = stream_text("s", "u", "test", service=failing)
    assert await anext(stream) == "one"
    with pytest.raises(LLMUnavailableError):
        await anext(stream)
