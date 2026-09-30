"""Example: SUBAGENT delegation (supervisor → specialist as a tool).

Use this shape when a task splits into specialist jobs whose inner work should not bloat the
main conversation (research, document analysis, data lookups). For a single agent with tools
see `agents/weather_agent`; for one-shot calls without an agent see `core/agents/llm.py`.
"""

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.research_supervisor_agent.tools import delegate_research
from api.core.agents.custom_providers import init_model
from api.core.agents.history_window import sliding_window_middleware
from api.core.agents.models import Models, model_capabilities_dict
from api.core.agents.schemas import AgentConfig, AgentSuggestionInstant
from api.core.agents.tenant_instructions import tenant_instructions_middleware

PRIMARY_MODEL = Models.OpenRouter.GLM_5_3_FLASH

config = AgentConfig(
    name="Supervisor de Pesquisa",
    description="Exemplo de subagente: delega pesquisas a um pesquisador especializado",
    system_prompt="""Você coordena pesquisas para o usuário.

- Para qualquer fato que exija fontes externas, chame `delegate_research` com uma pergunta
  autocontida. Divida perguntas compostas em chamadas separadas.
- Com os relatórios em mãos, escreva a resposta final: síntese clara em markdown, com os
  links das fontes que o pesquisador trouxe. Não invente dados que não vieram dos relatórios.
- Perguntas conceituais simples você responde direto, sem delegar.""",
    model=init_model(PRIMARY_MODEL),
    tools=[delegate_research],
    suggestions=[
        AgentSuggestionInstant(
            label="Comparar dois frameworks",
            prompt="Compare o estado atual do FastAPI e do Django para APIs async.",
        ),
    ],
    save_to_db=True,
    capabilities=model_capabilities_dict(PRIMARY_MODEL),
)


def create_root_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Factory called by the registry with the shared checkpointer."""
    return create_agent(
        model=config.model,
        tools=config.tools,
        system_prompt=config.system_prompt,
        middleware=[sliding_window_middleware, tenant_instructions_middleware],
        checkpointer=checkpointer,
    )
