# LangChain Agents

Esta pasta contém agentes implementados usando o framework LangChain, que são automaticamente descobertos e servidos pelo proxy LiteLLM.

## Estrutura

Cada agente deve seguir a seguinte estrutura:

```
langchain_agents/
├── nome_do_agente/
│   ├── __init__.py
│   ├── agent.py          # Arquivo principal com root_agent
│   └── tools/            # Pasta com as ferramentas (opcional)
│       ├── __init__.py
│       ├── tool1.py
│       └── tool2.py
```

## Exemplo de Agente

O agente deve ser definido no arquivo `agent.py` e exportar uma variável chamada `root_agent`:

```python
from langchain.agents import AgentType, initialize_agent
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage

# Configurar o modelo
llm = ChatOpenAI(
    model="gpt-4",
    openai_api_base="https://api.empresa.ia/v1",
    openai_api_key="sua-chave-aqui",
    temperature=0.3,
)

# Criar o agente
root_agent = initialize_agent(
    tools=[],  # Suas tools aqui
    llm=llm,
    agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True,
)

# Atributos necessários para compatibilidade
root_agent.name = "nome_do_agente"
root_agent.description = "Descrição do agente"
```

## Configuração da API

Para usar a API personalizada da empresa, configure o `ChatOpenAI` com:

- `openai_api_base`: "https://api.empresa.ia/v1"
- `openai_api_key`: Sua chave de API
- `model`: Modelo disponível na API

## Tools

As tools devem herdar de `BaseTool` do LangChain:

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class MinhaToolInput(BaseModel):
    parametro: str = Field(description="Descrição do parâmetro")

class MinhaTool(BaseTool):
    name = "minha_tool"
    description = "Descrição da tool"
    args_schema = MinhaToolInput

    def _run(self, parametro: str) -> str:
        # Implementação da tool
        return "resultado"

    async def _arun(self, parametro: str) -> str:
        return self._run(parametro)

# Instância para uso
minha_tool = MinhaTool()
```

## Descoberta Automática

O sistema automaticamente:

1. Escaneia a pasta `langchain_agents/`
2. Procura por subpastas com `agent.py`
3. Importa o `root_agent` de cada arquivo
4. Registra o agente com ID `langchain-{nome_da_pasta}`
5. Disponibiliza via API REST e OpenAI-compatible endpoints

## Uso via API

Depois de configurado, o agente estará disponível em:

- **Chat direto**: `POST /chat` com `model: "langchain-nome-do-agente"`
- **OpenAI compatible**: `POST /v1/chat/completions` com `model: "langchain-nome-do-agente"`
- **Lista de modelos**: `GET /v1/models`

## Exemplo Completo

Veja o agente de exemplo em `langchain_agents/example_agent/` que inclui:

- Calculadora matemática
- Ferramenta de busca simulada
- Configuração com API personalizada
- Memória de conversa
