from typing import Annotated, Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

SuggestionSection = Literal["direct", "template", "follow_up"]

# What clicking a suggestion chip does in the composer (optimuslar, 2026-09): `fill` only writes
# the text (the user reviews and sends); `attach` writes it, opens the file picker and sends by
# itself as soon as a file is attached — for flows that start from a document ("analyze this
# contract"). The frontend treats a missing/unknown value as `fill`.
SuggestionAction = Literal["fill", "attach"]


class AgentSuggestionInstant(BaseModel):
    kind: Literal["instant"] = "instant"
    label: str
    prompt: str
    section: SuggestionSection = "direct"
    action: SuggestionAction = "fill"
    emoji: str = ""


class AgentSuggestionTemplate(BaseModel):
    kind: Literal["template"] = "template"
    label: str
    template: str
    placeholders: list[str]
    section: SuggestionSection = "template"
    emoji: str = ""


AgentSuggestion = Annotated[
    AgentSuggestionInstant | AgentSuggestionTemplate,
    Field(discriminator="kind"),
]


class AgentConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    system_prompt: str
    model: BaseChatModel
    tools: list[BaseTool] = []
    suggestions: list[AgentSuggestion] = []
    save_to_db: bool = True
    # Capability flags exposed on GET /agents so the frontend blocks incompatible uploads
    # (e.g. an image on a text-only model). Fill with
    # ``model_capabilities_dict(Models.X.Y)`` from api.core.agents.models.
    capabilities: dict[str, bool] = Field(
        default_factory=lambda: {
            "image_input": False,
            "pdf_input": False,
            "audio_input": False,
            "video_input": False,
            "reasoning": False,
        }
    )


SUGGESTION_LABEL_MAX_CHARS = 56


def serialize_suggestions_for_api(suggestions: list[Any]) -> list[dict[str, Any]]:
    """JSON-serializable suggestion payloads for the agents list API (supports legacy plain strings)."""
    out: list[dict[str, Any]] = []
    for item in suggestions:
        if isinstance(item, str):
            label = (
                item
                if len(item) <= SUGGESTION_LABEL_MAX_CHARS
                else (item[: SUGGESTION_LABEL_MAX_CHARS - 3] + "...")
            )
            out.append(
                {
                    "kind": "instant",
                    "label": label,
                    "prompt": item,
                    "section": "direct",
                    "action": "fill",
                    "emoji": "",
                }
            )
        elif isinstance(item, BaseModel):
            out.append(item.model_dump(mode="json"))
        else:
            out.append(item)
    return out
