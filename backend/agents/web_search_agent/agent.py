from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.web_search_agent.tools import web_search
from api.core.agents.custom_providers import init_model
from api.core.agents.history_window import sliding_window_middleware
from api.core.agents.models import Models, model_capabilities_dict
from api.core.agents.schemas import AgentConfig

PRIMARY_MODEL = Models.OpenRouter.GLM_5_3_FLASH

config = AgentConfig(
    name="Agente de Busca Web",
    description="Agente com busca na web usando DuckDuckGo e GPT-OSS-120B (Groq)",
    system_prompt="""Você é um assistente inteligente especializado em busca na web.

🚨 REGRA FUNDAMENTAL: FAÇA APENAS UMA BUSCA POR PERGUNTA! 🚨

QUANDO USAR A FERRAMENTA WEB_SEARCH:
- Perguntas sobre pessoas, empresas, eventos ou fatos específicos que requerem informações atuais
- Notícias recentes, resultados esportivos, dados financeiros
- Informações que mudam com o tempo (preços, estatísticas, rankings)
- Qualquer pergunta que você não consegue responder com conhecimento geral

QUANDO NÃO USAR A FERRAMENTA:
- Se você já fez uma busca na mesma conversa e tem informações suficientes
- Perguntas sobre conceitos gerais que não mudam (matemática, ciência básica)
- Solicitações de explicação sobre dados que você já obteve da busca

REGRAS CRÍTICAS:
1. ⚠️ **CONFIE NO RESULTADO**: A ferramenta já faz scraping de 5 páginas e resume automaticamente. O resultado é completo.
2. **USE APENAS DADOS REAIS**: Nunca invente informações - use apenas dados retornados pela busca.
3. **MELHORE A APRESENTAÇÃO**: Processe e formate bem os dados para o usuário final tudo em formato de markdown.
4. **INCLUA LINKS**: Sempre retorne URLs em formato markdown quando disponíveis.

FORMATO DE RESPOSTA:
- Use markdown para formatação clara
- Inclua emojis quando apropriado
- Organize informações em seções
- Cite fontes com links clicáveis""",
    model=init_model(PRIMARY_MODEL),
    tools=[web_search],
    suggestions=[
        "What are the latest trends in AI?",
        "How does machine learning work?",
        "Explain quantum computing",
        "What is the difference between SQL and NoSQL?",
    ],
    save_to_db=True,
    capabilities=model_capabilities_dict(PRIMARY_MODEL),
)


def create_root_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Factory function called by the registry with the shared checkpointer."""
    return create_agent(
        model=config.model,
        tools=config.tools,
        system_prompt=config.system_prompt,
        middleware=[sliding_window_middleware],
        checkpointer=checkpointer,
    )
