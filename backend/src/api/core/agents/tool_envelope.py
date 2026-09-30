"""Standard envelope for tool results the chat frontend renders as cards.

A tool that wants a rich UI returns `{"type": <discriminator>, "data": {...}}`. The frontend
keeps a registry `Record<type, Component>` (`frontend/src/components/chat/tool-results/`) and
renders the matching card; unknown types — and plain strings/dicts without `type` — fall back
to the collapsed tool block. So the envelope is OPT-IN per tool: a tool whose output is only
reasoning input for the model (search hits, raw rows) should return plain data and let the
agent write the conclusion in text.

Discriminators must match the frontend registry keys exactly. Add app-specific types in the
app (next to the tools that emit them), not here. Origin: optimuslar (5 tool modules), 2026-09.
"""

from typing import Any, Final

RESULT_TYPE_ACTION_CONFIRMATION: Final = "action_confirmation"

ACTION_STATUS_SUCCESS: Final = "success"
ACTION_STATUS_ERROR: Final = "error"


def tool_result(result_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Wrap `data` in the envelope the frontend registry dispatches on."""
    return {"type": result_type, "data": data}


def action_confirmation(
    message: str, status: str = ACTION_STATUS_SUCCESS, **extras: Any
) -> dict[str, Any]:
    """ "Done: <message>" card for write actions (created, scheduled, sent...)."""
    return tool_result(
        RESULT_TYPE_ACTION_CONFIRMATION, {"status": status, "message": message, **extras}
    )


def action_error(message: str, **extras: Any) -> dict[str, Any]:
    """Same card in error state. Prefer this over raising for EXPECTED failures (validation,
    not found): the model reads the message and can recover; an exception aborts the turn."""
    return action_confirmation(message=message, status=ACTION_STATUS_ERROR, **extras)
