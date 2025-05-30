import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from google.adk.agents import Agent

from constants.ai_models import MODELS_MAPPING
from google_agents.generate_charts_agent.charts import generate_example_plot

BASE_DIR = pathlib.Path(__file__).parent.parent.parent


root_agent = Agent(
    name="generate_charts_agent",
    model=MODELS_MAPPING["gemini-2.0-flash-lite"],
    description="Agente especializado em geração de gráficos de exemplo.",
    instruction="""
Você é um agente responsável por criar gráficos de exemplo.

Instruções:
- Sempre chame `generate_example_plot` para gerar o gráfico.
- Retorne **apenas** o JSON resultante de `generate_example_plot`, sem texto adicional.
""",
    tools=[generate_example_plot],
)
