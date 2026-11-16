"""Process limiter + backoff now cover AGENT model calls, and an agent turn is bounded
(audit 2026-11-13 core-ai-04 / core-ai-09).

- `ChatOpenRouter` (what `init_model` returns) retries 429 with backoff and shares ONE limiter;
- streaming retries only before the first chunk reached the caller;
- `llm.complete` on top of the guarded model does not double the attempts (no 3x3);
- a model that keeps asking for a tool stops at `agent_recursion_limit` with a tratable message
  instead of looping to LangGraph's 10007 default.
"""

import anyio
import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import Field

from api.core.agents import llm, llm_limits
from api.core.agents.custom_providers import ChatOpenRouter
from api.core.agents.run_limits import (
    TURN_STEP_LIMIT_USER_MESSAGE,
    TURN_TIMEOUT_USER_MESSAGE,
    bounded_events,
)
from api.services.agents.executors import execute_agent
from config.settings import settings


class RateLimitedError(Exception):
    status_code = 429


class UnauthorizedError(Exception):
    status_code = 401


def _result(text: str = "ok") -> ChatResult:
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    monkeypatch.setattr(llm_limits, "_backoff_seconds", lambda _attempt: 0.0)


@pytest.fixture
def model():
    return ChatOpenRouter(model="anthropic/claude-haiku-5.5", openai_api_key="k", streaming=False)


@pytest.fixture
def streaming_model():
    return ChatOpenRouter(model="anthropic/claude-haiku-5.5", openai_api_key="k", streaming=True)


async def test_agent_model_recovers_from_two_429s(model, monkeypatch):
    calls = {"n": 0}

    async def flaky(self, *_a, **_k):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RateLimitedError("rate limit")
        return _result("depois do backoff")

    monkeypatch.setattr(ChatOpenAI, "_agenerate", flaky)
    reply = await model.ainvoke("oi")
    assert reply.content == "depois do backoff"
    assert calls["n"] == 3


async def test_non_transient_error_is_not_retried(model, monkeypatch):
    calls = {"n": 0}

    async def bad_key(self, *_a, **_k):
        calls["n"] += 1
        raise UnauthorizedError("invalid key")

    monkeypatch.setattr(ChatOpenAI, "_agenerate", bad_key)
    with pytest.raises(UnauthorizedError):
        await model.ainvoke("oi")
    assert calls["n"] == 1


async def test_concurrent_agent_calls_never_exceed_the_limiter(model, monkeypatch):
    monkeypatch.setattr(llm_limits, "_limiter", anyio.CapacityLimiter(2))
    state = {"now": 0, "peak": 0}

    async def slow(self, *_a, **_k):
        state["now"] += 1
        state["peak"] = max(state["peak"], state["now"])
        await anyio.sleep(0.02)
        state["now"] -= 1
        return _result()

    monkeypatch.setattr(ChatOpenAI, "_agenerate", slow)
    async with anyio.create_task_group() as tg:
        for _ in range(8):
            tg.start_soon(model.ainvoke, "oi")
    assert state["peak"] == 2


async def test_stream_retries_only_before_the_first_chunk(streaming_model, monkeypatch):
    attempts = {"n": 0}

    async def flaky_stream(self, *_a, **_k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RateLimitedError("rate limit")
        yield ChatGenerationChunk(message=AIMessageChunk(content="a"))
        yield ChatGenerationChunk(message=AIMessageChunk(content="b"))

    monkeypatch.setattr(ChatOpenAI, "_astream", flaky_stream)
    text = "".join([c.content async for c in streaming_model.astream("oi")])
    assert text == "ab" and attempts["n"] == 2

    attempts["n"] = 0

    async def dies_midway(self, *_a, **_k):
        attempts["n"] += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="a"))
        raise RateLimitedError("rate limit")

    monkeypatch.setattr(ChatOpenAI, "_astream", dies_midway)
    with pytest.raises(RateLimitedError):
        _ = [c async for c in streaming_model.astream("oi")]
    assert attempts["n"] == 1  # a replay would duplicate the partial text for the client


async def test_complete_on_top_of_the_guarded_model_does_not_multiply_attempts(model, monkeypatch):
    calls = {"n": 0}

    async def flaky(self, *_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitedError("rate limit")
        return _result("ok")

    monkeypatch.setattr(ChatOpenAI, "_agenerate", flaky)
    monkeypatch.setattr(llm, "init_model", lambda *_a, **_k: model)
    result = await llm.complete("oi", usage=None)
    assert result.text == "ok"
    assert calls["n"] == 2  # one retry total (outer wrapper only), not 2 x 3


class LoopingModel(FakeMessagesListChatModel):
    """Always answers with a NEW tool call: the loop an agent must not run forever.

    Tool-call ids must be unique, otherwise LangGraph sees an already-answered call and routes
    back to the model node (a different failure that has nothing to do with the step cap).
    """

    calls: list[int] = Field(default_factory=list)

    def bind_tools(self, tools, **_kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.calls.append(1)
        call = {"name": "ping", "args": {}, "id": f"call-{len(self.calls)}"}
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[call]))]
        )


@tool
def ping() -> str:
    """Pings."""
    return "pong"


async def test_agent_turn_stops_at_the_recursion_limit(monkeypatch):
    monkeypatch.setattr(settings.agents, "agent_recursion_limit", 6)
    model = LoopingModel(responses=[AIMessage(content="")], calls=[])
    agent = create_agent(model=model, tools=[ping], system_prompt="teste")
    reply = await execute_agent({"agent": agent}, "oi", "thread-1", agent_id="loop")
    assert TURN_STEP_LIMIT_USER_MESSAGE in reply
    assert 0 < len(model.calls) <= 6  # nowhere near LangGraph's 10007 default


async def test_execute_agent_enforces_the_turn_timeout(monkeypatch):
    monkeypatch.setattr(settings.agents, "agent_turn_timeout_seconds", 0.05)

    class Slow:
        async def ainvoke(self, *_a, **_k):
            await anyio.sleep(5)

    reply = await execute_agent({"agent": Slow()}, "oi", "thread-2", agent_id="slow")
    assert TURN_TIMEOUT_USER_MESSAGE in reply


async def test_bounded_events_cuts_a_stalled_stream():
    async def stalled():
        yield 1
        await anyio.sleep(5)
        yield 2

    seen = []
    with pytest.raises(TimeoutError):
        async for event in bounded_events(stalled(), 0.1):
            seen.append(event)
    assert seen == [1]
