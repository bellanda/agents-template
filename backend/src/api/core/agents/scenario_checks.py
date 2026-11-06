"""Expectation checks of the scenario replay (`scenario_replay.py` ships/needs this module too).

Pure functions: each takes the scenario's `expect` mapping plus what the agent did and returns
human-readable failure strings (empty = pass). `calls` items only need `.name` and `.args`.
"""

import re
from typing import Any

REPLY_PREVIEW_CHARS = 120


def is_silent_reply(reply: str, silence_token: str) -> bool:
    return not reply.strip() or reply.strip() == silence_token


def preview(text: str) -> str:
    return text if len(text) <= REPLY_PREVIEW_CHARS else text[:REPLY_PREVIEW_CHARS] + "…"


def check_handoff(
    expect: dict[str, Any],
    calls: list[Any],
    handoff_tool: str,
    reason_keys: tuple[str, ...],
) -> list[str]:
    if "handoff" not in expect:
        return []
    handoffs = [c for c in calls if c.name == handoff_tool]
    if bool(expect["handoff"]) != bool(handoffs):
        return [f"expected handoff={expect['handoff']}, got {len(handoffs)} {handoff_tool} call(s)"]
    failures: list[str] = []
    reasons = " ".join(str(c.args.get(key, "")) for c in handoffs for key in reason_keys)
    for pattern in expect.get("handoff_reason_must_match", []):
        if not re.search(pattern, reasons, re.IGNORECASE):
            failures.append(f"handoff reason did not match /{pattern}/: {preview(reasons)!r}")
    return failures


def check_tools(expect: dict[str, Any], calls: list[Any]) -> list[str]:
    names = {c.name for c in calls}
    failures = [
        f"expected tool {n!r} to be called, it was not"
        for n in expect.get("tools_called", [])
        if n not in names
    ]
    failures += [
        f"tool {n!r} must not be called, but was"
        for n in expect.get("tools_not_called", [])
        if n in names
    ]
    return failures


def check_replies(expect: dict[str, Any], replies: list[str], silence_token: str) -> list[str]:
    failures: list[str] = []
    spoken = [r for r in replies if not is_silent_reply(r, silence_token)]
    if "silent" in expect and bool(expect["silent"]) != (not spoken):
        failures.append(
            f"expected silent={expect['silent']}, got {len(spoken)} non-silent reply(ies): {preview(' | '.join(spoken))!r}"
        )
    for pattern in expect.get("reply_must_not_match", []):
        for position, reply in enumerate(replies, start=1):
            if re.search(pattern, reply, re.IGNORECASE):
                failures.append(
                    f"reply {position} matched forbidden /{pattern}/: {preview(reply)!r}"
                )
    for pattern in expect.get("last_reply_must_match", []):
        last = spoken[-1] if spoken else ""
        if not re.search(pattern, last, re.IGNORECASE):
            failures.append(f"last reply did not match /{pattern}/: {preview(last)!r}")
    for pattern, limit in expect.get("max_matches", {}).items():
        found = sum(len(re.findall(pattern, reply, re.IGNORECASE)) for reply in replies)
        if found > limit:
            failures.append(f"/{pattern}/ matched {found}x across replies, max {limit}")
    return failures
