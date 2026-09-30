"""Example: an AGENT WITH TOOLS — the common case of the template.

`config` + `create_root_agent` is the whole contract (registry auto-discovers `agents/<name>/`).
Middleware order: history window first (trims what the model sees), tenant instructions last
(appends the tenant's Markdown to the system prompt). See AGENTS_SUBSYSTEM.md §3.
"""

from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.weather_agent.tools import get_weather
from api.core.agents.custom_providers import init_model
from api.core.agents.history_window import sliding_window_middleware
from api.core.agents.models import Models, model_capabilities_dict
from api.core.agents.schemas import AgentConfig
from api.core.agents.tenant_instructions import tenant_instructions_middleware

PRIMARY_MODEL = Models.OpenRouter.GLM_5_3_FLASH

config = AgentConfig(
    name="Agente de Clima",
    description="Exemplo de agente com tools: clima atual por cidade",
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
    model=init_model(PRIMARY_MODEL, max_tokens=5000),
    tools=[get_weather],
    save_to_db=True,
    capabilities=model_capabilities_dict(PRIMARY_MODEL),
)


def create_root_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Factory function called by the registry with the shared checkpointer."""
    return create_agent(
        model=config.model,
        tools=config.tools,
        system_prompt=config.system_prompt,
        middleware=[sliding_window_middleware, tenant_instructions_middleware],
        checkpointer=checkpointer,
    )
