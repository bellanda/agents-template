from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict


class AgentConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    system_prompt: str
    model: BaseChatModel
    tools: list[BaseTool] = []
    suggestions: list[str] = []
    save_to_db: bool = True
