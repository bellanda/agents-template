"""The models a tenant (or the chat picker) may choose — label + price for the UI.

Today it is ONE model, and that is the decision, not an incomplete state: the whole stack
runs on OpenRouter GLM 5.3 Flash, which keeps inference jurisdiction auditable in one place
(`provider_order` in models.py). The catalog still exists because it carries the LABEL and
PRICE shown on screen — the account owner's decision is cost per run — and because a second
option enters here without touching routes or schema. Served at `GET /agents/model-catalog`.

Rule that does not change: only models whose credentials the product actually configures.
Offering a slug without a key turns the user's choice into a run that fails later, far from
the screen where they chose it. Origin: akmeo `services/agents/model_catalog.py`, 2026-09.
"""

from dataclasses import dataclass
from typing import Any, Final

from api.core.agents.models import (
    ModelConfig,
    Models,
    find_model_config_by_id,
    model_capabilities_dict,
)


@dataclass(frozen=True, slots=True)
class ModelOption:
    config: ModelConfig
    label: str
    description: str

    @property
    def model_id(self) -> str:
        return self.config.model_id

    def to_api(self) -> dict[str, Any]:
        return {
            "model_id": self.config.model_id,
            "label": self.label,
            "provider": self.config.provider,
            "description": self.description,
            "input_price_per_1m": self.config.input_price_per_1m,
            "cached_input_price_per_1m": self.config.cached_input_price_per_1m,
            "output_price_per_1m": self.config.output_price_per_1m,
            "capabilities": model_capabilities_dict(self.config),
        }


AGENT_MODELS: Final[tuple[ModelOption, ...]] = (
    ModelOption(
        Models.OpenRouter.GLM_5_3_FLASH,
        "GLM 5.3 Flash",
        "Modelo padrão: texto, imagem e vídeo. Processamento nos EUA e custo real por chamada.",
    ),
)

DEFAULT_MODEL_ID: Final = AGENT_MODELS[0].model_id
MODEL_IDS: Final[frozenset[str]] = frozenset(option.model_id for option in AGENT_MODELS)


def exists(model_id: str) -> bool:
    return model_id in MODEL_IDS


def label_for(model_id: str) -> str:
    """Catalog label, or the raw id for a model that left the catalog — keeps old configs
    legible instead of showing "unknown"."""
    for option in AGENT_MODELS:
        if option.model_id == model_id:
            return option.label
    return model_id


def catalog_payload() -> list[dict[str, Any]]:
    return [option.to_api() for option in AGENT_MODELS]


def _validate() -> None:
    """Fail at import if the catalog points at a slug outside the registry."""
    unknown = [o.model_id for o in AGENT_MODELS if find_model_config_by_id(o.model_id) is None]
    if unknown:
        raise RuntimeError(f"Models outside the registry in AGENT_MODELS: {unknown}")


_validate()
