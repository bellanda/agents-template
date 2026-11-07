"""Regressions ported from Kailos: doubled model id in usage rows (2026-10-22) and an empty
customer-facing reply right after a tool call (2026-11-05)."""

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from pydantic import Field

from api.core.agents.empty_reply_guard import (
    EMPTY_REPLY_RETRY_INSTRUCTION,
    empty_reply_guard_middleware,
)
from api.repositories.agents.usage import build_usage_from_ai_message, collapse_repeated_model_id

HAIKU = "anthropic/claude-haiku-5.5"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (HAIKU * 2, HAIKU),
        (HAIKU, HAIKU),
        ("z-ai/glm-5.3-flash" * 2, "z-ai/glm-5.3-flash"),
        ("abc", "abc"),
    ],
)
def test_collapse_repeated_model_id(raw, expected):
    assert collapse_repeated_model_id(raw) == expected


def test_usage_row_stores_a_single_model_id_when_streaming_doubled_it():
    ai = AIMessage(
        content="oi",
        usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        response_metadata={"model_provider": "openrouter", "model_name": HAIKU * 2},
    )
    row = build_usage_from_ai_message(ai, thread_id="t", message_id="m", agent_id="a")
    assert row is not None
    assert row.model_id == HAIKU


class ScriptedChatModel(FakeMessagesListChatModel):
    """Replays scripted AI messages and records what each call was shown."""

    seen: list[list] = Field(default_factory=list)

    def bind_tools(self, tools, **_kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


@tool
def register_note() -> str:
    """Registers a note."""
    return "Registrado."


async def run_scripted_turn(script: list[AIMessage]) -> tuple[ScriptedChatModel, list]:
    model = ScriptedChatModel(responses=script, seen=[])
    agent = create_agent(
        model=model,
        tools=[register_note],
        system_prompt="teste",
        middleware=[empty_reply_guard_middleware],
    )
    result = await agent.ainvoke({"messages": [HumanMessage(content="já comprei")]})
    return model, result["messages"]


TOOL_CALL = AIMessage(content="", tool_calls=[{"name": "register_note", "args": {}, "id": "1"}])


async def test_empty_turn_after_a_tool_gets_one_retry_with_an_explicit_instruction():
    model, messages = await run_scripted_turn(
        [TOOL_CALL, AIMessage(content=""), AIMessage(content="Valeu!")]
    )
    assert messages[-1].content == "Valeu!"
    assert len(model.seen) == 3  # tool call, empty answer, retry
    assert EMPTY_REPLY_RETRY_INSTRUCTION in str(model.seen[-1][-1].content)
    # The instruction is request-only: it never lands in the persisted thread.
    assert all(EMPTY_REPLY_RETRY_INSTRUCTION not in str(m.content) for m in messages)


async def test_a_normal_reply_after_a_tool_is_not_retried():
    model, messages = await run_scripted_turn([TOOL_CALL, AIMessage(content="Anotado!")])
    assert messages[-1].content == "Anotado!"
    assert len(model.seen) == 2
