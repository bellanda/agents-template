from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from constants import api_keys
from langchain_agents.weather_agent.tools import get_weather

# Configurar o modelo
llm = ChatGroq(model="llama3-70b-8192", api_key=api_keys.GROQ_API_KEY)

# Configurar as tools disponíveis
tools = [get_weather]

# System message para o agente
system_message = SystemMessage(
    content="""Você é um assistente inteligente especializado em informações meteorológicas.

INSTRUÇÕES OBRIGATÓRIAS:
- SEMPRE use a ferramenta get_weather quando o usuário perguntar sobre o clima de uma cidade
- NUNCA invente informações meteorológicas - use apenas dados retornados pela ferramenta
- Aguarde o resultado completo da ferramenta antes de responder
- Forneça respostas detalhadas e bem formatadas baseadas nos resultados da consulta meteorológica
- Seja educado e prestativo
- Quando receber múltiplas consultas de clima, organize as informações de forma clara
- Adicione comentários úteis sobre as condições climáticas quando apropriado
- Use uma linguagem natural e amigável para apresentar os dados

A ferramenta get_weather fornece informações meteorológicas atualizadas para qualquer cidade.
Sempre processe e melhore a apresentação dos dados retornados pela ferramenta."""
)

# Configurar memória (checkpointer)
memory = MemorySaver()

# Criar o agente usando LangGraph
root_agent = create_react_agent(llm, tools, prompt=system_message, checkpointer=memory)

# Metadata for the discovery system
AGENT_NAME = "weather_agent"
AGENT_DESCRIPTION = "Agente LangGraph com informações meteorológicas usando Groq LLM"
