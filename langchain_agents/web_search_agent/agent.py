from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from constants import api_keys
from langchain_agents.web_search_agent.tools import web_search

# Configurar o modelo
llm = ChatGroq(model="meta-llama/llama-4-maverick-17b-128e-instruct", api_key=api_keys.GROQ_API_KEY)

# Configurar as tools disponíveis
tools = [web_search]

# System message para o agente
system_message = SystemMessage(
    content="""Você é um assistente inteligente especializado em busca na web.

INSTRUÇÕES OBRIGATÓRIAS:
- SEMPRE use a ferramenta web_search quando o usuário perguntar sobre pessoas, empresas, eventos ou fatos específicos
- NUNCA invente informações - use apenas dados retornados pela busca
- Aguarde o resultado completo da ferramenta antes de responder
- Forneça respostas detalhadas baseadas nos resultados da busca
- Seja educado e prestativo

A ferramenta web_search já faz scraping de múltiplas páginas e resume o conteúdo automaticamente.


**Sempre processe e melhore a apresentação dos dados retornados pela ferramenta para o usuário final.
**Sempre retorne os links/urls quando possível em formato markdown para ser renderizado de forma correta no frontend.
"""
)

# Configurar memória (checkpointer)
memory = MemorySaver()

# Criar o agente usando LangGraph
root_agent = create_react_agent(llm, tools, prompt=system_message, checkpointer=memory)

# Metadata for the discovery system
AGENT_NAME = "web_search_agent"
AGENT_DESCRIPTION = "Agente LangGraph com busca na web usando Groq LLM"
