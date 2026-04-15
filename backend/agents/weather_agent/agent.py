from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.weather_agent.tools import get_weather
from api.core.agents.custom_providers import init_model
from api.core.agents.models import Models
from api.core.agents.schemas import AgentConfig

config = AgentConfig(
    name="Agente de Clima",
    description="Agente com informações meteorológicas usando GPT-OSS-20B (Groq)",
    system_prompt="""Você é um assistente inteligente especializado em informações meteorológicas.

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
""",
    model=init_model(Models.Chutes.DEEPSEEK_V3_2_TEE, max_tokens=5000),
    tools=[get_weather],
    save_to_db=True,
)


def create_root_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Factory function called by the registry with the shared checkpointer."""
    return create_agent(
        model=config.model,
        tools=config.tools,
        system_prompt=config.system_prompt,
        checkpointer=checkpointer,
    )
