from typing import Annotated, Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

SuggestionSection = Literal["direct", "template", "follow_up"]


class AgentSuggestionInstant(BaseModel):
    kind: Literal["instant"] = "instant"
    label: str
    prompt: str
    section: SuggestionSection = "direct"
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
                    "emoji": "",
                }
            )
        elif isinstance(item, BaseModel):
            out.append(item.model_dump(mode="json"))
        else:
            out.append(item)
    return out
