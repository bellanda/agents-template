from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver

from agents.weather_agent.tools import get_weather
from environment import api_keys

# Configurar o modelo com parâmetros para reduzir repetições
model = init_chat_model(
    model="groq:openai/gpt-oss-20b",
    api_key=api_keys.GROQ_API_KEY,
    streaming=True,
)

# Configurar as tools disponíveis
tools = [get_weather]

# System message para o agente
SYSTEM_PROMPT = """Você é um assistente inteligente especializado em informações meteorológicas.

🚨 REGRA FUNDAMENTAL: USE SEMPRE A FERRAMENTA GET_WEATHER PARA CONSULTAS DE CLIMA! 🚨

QUANDO USAR A FERRAMENTA GET_WEATHER:
- Perguntas sobre o clima de cidades específicas
- Solicitações de previsão do tempo
- Qualquer dúvida sobre condições meteorológicas atuais

REGRAS CRÍTICAS:
1. ⚠️ CONFIE NO RESULTADO: Use apenas dados retornados pela ferramenta get_weather.
2. NÃO INVENTE INFORMAÇÕES: Nunca gere dados meteorológicos sem consultar a ferramenta.
3. MELHORE A APRESENTAÇÃO: Processe e formate bem os dados para o usuário final, tudo em formato de markdown.
4. ORGANIZE RESPOSTAS: Quando houver múltiplas cidades, organize as informações de forma clara.
5. ADICIONE COMENTÁRIOS: Inclua comentários úteis sobre as condições climáticas quando apropriado.

FORMATO DE RESPOSTA:
- Use markdown para formatação clara
- Inclua emojis quando apropriado
- Organize informações em seções
- Seja educado e prestativo
"""

# Configurar memória (checkpointer)
checkpointer = MemorySaver()

# Criar o agente usando LangGraph
root_agent = create_agent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

# Metadata for the discovery system
AGENT_NAME = "Agente de Clima"
AGENT_DESCRIPTION = "Agente com informações meteorológicas usando GPT-OSS-20B (Groq)"
