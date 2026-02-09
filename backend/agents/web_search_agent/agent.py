from langchain.agents import create_agent

# from langchain.chat_models import init_chat_model
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.web_search_agent.tools import web_search
from config.agents import init_cerebras_model

# Agent metadata for the discovery system
AGENT_NAME = "Agente de Busca Web"
AGENT_DESCRIPTION = "Agente com busca na web usando DuckDuckGo e MiniMax-M2 (Chutes)"
AGENT_MODE = "chat"  # Each search is independent, no conversation memory
AGENT_SUGGESTIONS = [
    "What are the latest trends in AI?",
    "How does machine learning work?",
    "Explain quantum computing",
    "What is the difference between SQL and NoSQL?",
]

# # Model configuration (Chutes wrapper with reasoning capture)
# model = init_chutes_model(
#     model="zai-org/GLM-4.7-TEE",
#     streaming=True,
#     max_tokens=4096,
# )

# Model configuration (Cerebras wrapper with reasoning capture)
model = init_cerebras_model(
    model="zai-glm-4.7",
    temperature=0.7,
    max_tokens=4096,
    streaming=True,
)

# model = init_chat_model(
#     model="nvidia:openai/gpt-oss-120b",
#     api_key=api_keys.NVIDIA_API_KEY,
#     streaming=True,
#     max_tokens=4096,
# )

# Available tools
tools = [web_search]

# System prompt
SYSTEM_PROMPT = """Você é um assistente inteligente especializado em busca na web.

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
- Cite fontes com links clicáveis"""


def create_root_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Factory function called by the registry with the shared checkpointer."""
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
