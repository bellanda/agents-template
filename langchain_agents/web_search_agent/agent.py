from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent

from constants import api_keys
from langchain_agents.web_search_agent.tools import web_search

# Configurar o modelo com parâmetros para reduzir repetições
model = init_chat_model(
    "groq:openai/gpt-oss-20b",
    api_key=api_keys.GROQ_API_KEY,
    temperature=0.1,
    max_tokens=8000,
    verbose=True,
    streaming=True,
)

# Configurar as tools disponíveis
tools = [web_search]

# System message para o agente
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


checkpointer = InMemorySaver()

root_agent = create_react_agent(
    model=model,
    tools=[web_search],
    prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

# Metadata for the discovery system
AGENT_NAME = "web_search_agent"
AGENT_DESCRIPTION = "Agente LangGraph com busca na web usando Groq LLM"
