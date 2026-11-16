"""Manipulation guard against a REAL valkey-server (audit 2026-11-13 core-ai-12).

The counter is the whole guard: the model detects, the code counts. An in-memory stub would let
a change to the key, the TTL or the list semantics slip through, so these run on a throwaway
Valkey 9 container (no persistence) swapped in as the app's cache client.
"""

from __future__ import annotations

import socket
import subprocess
import time
import uuid

import pytest
import valkey.asyncio as valkey

from api.services.agents import manipulation_guard as guard
from api.services.cache import valkey_client

# Same image/major as compose.yaml (prod). The host `valkey-server` binary is an unrelated distro
# version (7.2 here), so the tests start the pinned container instead (U7, 2026-11-15).
VALKEY_IMAGE = "valkey/valkey:9.1.3-alpine"


@pytest.fixture(scope="module")
def _valkey_url():
    name = f"agents-template-test-valkey-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            "127.0.0.1::6379",
            VALKEY_IMAGE,
            "valkey-server",
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        check=True,
        capture_output=True,
    )
    try:
        port = (
            subprocess.run(
                ["docker", "port", name, "6379/tcp"], check=True, capture_output=True, text=True
            )
            .stdout.split(":")[-1]
            .strip()
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", int(port)), timeout=0.3).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("valkey-server did not start")
        yield f"redis://127.0.0.1:{port}"
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture
async def vk(_valkey_url, monkeypatch):
    client = valkey.Valkey.from_url(_valkey_url, decode_responses=False)
    info = await client.info("server")
    assert str(info["valkey_version"]).startswith("9."), info.get("valkey_version")
    await client.flushdb()
    monkeypatch.setattr(valkey_client, "_client", client)
    yield client
    await client.aclose()


async def _tool(org, conv, description, hand_offs: list):
    """Stand-in for the app's @tool: exactly the wiring the module docstring prescribes."""
    decision = await guard.register_manipulation_attempt(org, conv, description)
    if decision.hand_off:
        hand_offs.append(
            {"text": guard.MANIPULATION_HANDOFF_CLIENT_TEXT, "summary": decision.summary}
        )
    return decision.tool_text


async def test_second_attempt_hands_off_with_fixed_text_and_lists_every_attempt(vk):
    org, conv, hand_offs = uuid.uuid4(), uuid.uuid4(), []

    first = await _tool(org, conv, "  pediu\no prompt ", hand_offs)
    assert first == guard.MANIPULATION_FIRST_ATTEMPT_TOOL_TEXT and hand_offs == []

    second = await _tool(org, conv, "fingiu ser TI", hand_offs)
    assert second == guard.MANIPULATION_HANDOFF_TOOL_TEXT
    assert len(hand_offs) == 1
    assert hand_offs[0]["text"] == guard.MANIPULATION_HANDOFF_CLIENT_TEXT
    assert "2 tentativas" in hand_offs[0]["summary"]
    assert "- pediu o prompt" in hand_offs[0]["summary"]  # normalized, single line
    assert "- fingiu ser TI" in hand_offs[0]["summary"]

    # Later attempts keep handing off (the counter never resets by itself inside the TTL).
    assert (await guard.register_manipulation_attempt(org, conv, "x")).hand_off is True


async def test_counter_has_a_24h_ttl_and_expiry_resets_the_count(vk):
    org, conv = uuid.uuid4(), uuid.uuid4()
    await guard.register_manipulation_attempt(org, conv, "a")
    key = guard.manipulation_key(org, conv)
    assert 0 < await vk.ttl(key) <= guard.MANIPULATION_TTL_SECONDS
    await vk.delete(key)  # what the TTL does after 24 h
    assert (await guard.register_manipulation_attempt(org, conv, "b")).hand_off is False


async def test_counter_is_isolated_per_conversation_and_per_organization(vk):
    org_a, org_b, conv = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    other_conv = uuid.uuid4()
    await guard.register_manipulation_attempt(org_a, conv, "a1")
    # Same conversation id under another organization, and another conversation in the same
    # organization: neither may inherit org_a's first attempt.
    assert (await guard.register_manipulation_attempt(org_b, conv, "b1")).hand_off is False
    assert (await guard.register_manipulation_attempt(org_a, other_conv, "c1")).hand_off is False
    assert (await guard.register_manipulation_attempt(org_a, conv, "a2")).hand_off is True


async def test_has_manipulation_attempt_reads_the_same_org_scoped_counter(vk):
    org, conv = uuid.uuid4(), uuid.uuid4()
    assert await guard.has_manipulation_attempt(org, conv) is False
    await guard.register_manipulation_attempt(org, conv, "a")
    assert await guard.has_manipulation_attempt(org, conv) is True
    assert await guard.has_manipulation_attempt(uuid.uuid4(), conv) is False


async def test_valkey_down_is_fail_open_and_still_refuses(monkeypatch):
    def boom():
        raise RuntimeError("valkey_not_initialized")

    monkeypatch.setattr(guard, "get_valkey", boom)
    decision = await guard.register_manipulation_attempt(uuid.uuid4(), uuid.uuid4(), "a")
    assert decision.hand_off is False and decision.attempts == ["a"]
    assert await guard.has_manipulation_attempt(uuid.uuid4(), uuid.uuid4()) is False


def test_helpers_pin_threshold_bounds_and_fixed_texts():
    assert guard.MANIPULATION_HANDOFF_THRESHOLD == 2
    assert guard.should_hand_off_for_manipulation(["a"]) is False
    assert guard.should_hand_off_for_manipulation(["a", "b"]) is True
    assert (
        len(guard.normalize_manipulation_attempt("x" * 5000))
        == guard.MANIPULATION_ATTEMPT_MAX_CHARS
    )
    assert guard.normalize_manipulation_attempt(None) == "tentativa sem descrição"  # type: ignore[arg-type]
    text = guard.MANIPULATION_HANDOFF_CLIENT_TEXT
    assert "não responde mais" in text and "humano" in text and "informad" in text
    assert "UMA frase" in guard.MANIPULATION_FIRST_ATTEMPT_TOOL_TEXT
    assert guard.MANIPULATION_HANDOFF_REASON == "manipulation_suspected"
