"""The supervisor's only tool: hand a research question to the researcher SUBAGENT.

The researcher is a full agent (own prompt + `web_search` + its own tool loop). The supervisor
never sees its searches or scraped pages — only the final answer returned here — which keeps
the supervisor's context small no matter how much the researcher reads.
"""

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from agents.web_search_agent.tools import web_search
from api.core.agents.custom_providers import init_model
from api.core.agents.models import Models
from api.core.agents.subagents import run_subagent

RESEARCHER_NAME = "researcher"
RESEARCHER_MAX_TOKENS = 3000
RESEARCHER_PROMPT = """Você é um pesquisador. Receba UMA pergunta, pesquise na web com a
ferramenta web_search (no máximo duas buscas) e devolva um relatório curto e factual em
markdown, com os links das fontes. Não converse com o usuário: seu leitor é outro agente."""

# Built once at import (stateless: `checkpointer=False`, see core/agents/subagents.py).
researcher = create_agent(
    model=init_model(Models.OpenRouter.GLM_5_3_FLASH, max_tokens=RESEARCHER_MAX_TOKENS),
    tools=[web_search],
    system_prompt=RESEARCHER_PROMPT,
    checkpointer=False,
    name=RESEARCHER_NAME,
)


@tool("delegate_research")
async def delegate_research(question: str, config: RunnableConfig) -> str:
    """Delega uma pergunta de pesquisa a um pesquisador especializado que busca na web.

    Use para qualquer fato atual, notícia, dado ou comparação que exija fontes externas.
    Envie UMA pergunta autocontida por chamada (o pesquisador não vê a conversa). Para
    comparar dois assuntos, faça duas chamadas separadas.

    Args:
        question: A pergunta completa e autocontida a ser pesquisada.
    """
    return await run_subagent(researcher, question, name=RESEARCHER_NAME, parent_config=config)
