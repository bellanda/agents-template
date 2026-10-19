"""Real cost stamped from OpenRouter's `usage`, with and without BYOK.

Regression (2026-10-19): with our Anthropic key registered as BYOK in OpenRouter, a live call
returned `usage.cost = 0` and the inference price only in `cost_details.upstream_inference_cost`.
Reading `usage.cost` alone recorded every tenant's AI spend as zero. Payloads below are trimmed
from that live response.
"""

import pytest

from api.core.agents.custom_providers import ChatOpenRouter


def stamped_cost(usage: dict) -> float | None:
    target: dict = {}
    model = ChatOpenRouter(model="anthropic/claude-haiku-5.5", api_key="test")
    model._stamp_openrouter_metadata(target, {"provider": "Anthropic", "usage": usage})
    assert target["model_provider"] == "openrouter"
    return target.get("provider_cost_usd")


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        # Inside the BYOK free allowance: fee 0, inference billed to our key.
        (
            {"cost": 0, "is_byok": True, "cost_details": {"upstream_inference_cost": 0.0000035}},
            0.0000035,
        ),
        # Past the allowance: OpenRouter's fee on top of the inference.
        (
            {
                "cost": 0.0000002,
                "is_byok": True,
                "cost_details": {"upstream_inference_cost": 0.0000035},
            },
            0.0000037,
        ),
        # OpenRouter's own capacity (BYOK fallback or no key): `usage.cost` is already the total.
        (
            {
                "cost": 0.0000035,
                "is_byok": False,
                "cost_details": {"upstream_inference_cost": None},
            },
            0.0000035,
        ),
        ({}, None),
    ],
)
def test_recorded_cost_includes_byok_inference(usage, expected):
    assert stamped_cost(usage) == pytest.approx(expected)
