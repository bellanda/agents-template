import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from google.adk.agents import Agent

from constants.ai_models import MODELS_MAPPING
from google_agents.database_query_agent.database import do_database_query, get_database_documentation

BASE_DIR = pathlib.Path(__file__).parent.parent.parent


root_agent = Agent(
    name="database_query_agent",
    model=MODELS_MAPPING["gemini-2.0-flash-lite"],
    description="Agent specialized in database queries. You make SELECT queries only on Oracle database tables.",
    instruction=(
        """
Você é um agente de consultas Oracle.

PASSOS OBRIGATÓRIOS
1. Chame **get_database_documentation** para entender o esquema.

2. Gere **apenas** consultas **SELECT** válidas para Oracle  
    - nunca inclua `;` no final.

3. Execute a consulta chamando  
    `do_database_query(query="<SUA_QUERY_SQL>")`.

4. O dicionário retornado terá:
    - `url`  ........ link para o JSON com os dados  
    - `query_success` (bool)  
    - (opcional) `error`
    Se existir `error`, elabore outra query e repita o passo 3.
    
5. Quando `query_success == True`, devolva ao próximo modelo **somente**:

```json
{
    "query_url": "<valor de url>",
    "preview": "<breve descrição dos dados>"
}
```
        """
    ),
    tools=[get_database_documentation, do_database_query],
)
