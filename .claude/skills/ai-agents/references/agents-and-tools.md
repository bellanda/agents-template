# Agentes com tools

> Reference do gate `ai-agents`. Canônico: `backend/agents/weather_agent/` (caso comum),
> `backend/src/api/services/agents/registry.py`, `backend/AGENTS_SUBSYSTEM.md` §3.1.

## Contrato de `agents/<name>/agent.py`

```python
config = AgentConfig(
    name="…", description="…", system_prompt=SYSTEM_PROMPT,
    model=init_model(Models.OpenRouter.GLM_5_3_FLASH),
    tools=[tool_a, tool_b], save_to_db=True,
    capabilities=model_capabilities_dict(Models.OpenRouter.GLM_5_3_FLASH),
    suggestions=[AgentSuggestionInstant(label="…", prompt="…")],
)

def create_root_agent(checkpointer=None):          # o registry injeta o checkpointer compartilhado
    return create_agent(
        model=config.model, tools=config.tools, system_prompt=config.system_prompt,
        middleware=[sliding_window_middleware, tenant_instructions_middleware],
        checkpointer=checkpointer,
    )
```

- **Sem grafo manual** no caso comum: agente = modelo + system prompt + tools + middleware + checkpointer.
- **Ordem do middleware:** janela de histórico primeiro (corta o que o modelo vê), instruções do tenant
  por último (anexam ao system prompt). Agente que não lê config do tenant omite o segundo.
- **Auto-discovery** (`registry.py`): varre `agents/`, importa `agents.<name>.agent`, lê `config` +
  `create_root_agent` (ou `root_agent`), injeta checkpointer se `save_to_db=True`, anexa `usage_recorder`.
  Chave do registro = `model_id` (`_`→`-`). Import quebrado aparece como `agent_discovery_failed` no log
  (antes sumia do picker em silêncio).
- `system_prompt` = regras da PLATAFORMA (tools, segurança, disclosure); o que é do negócio entra via
  instruções do tenant (`tenant-config.md`), nunca colado no prompt de código.
- Agente por tenant sem dados fixos: dados do negócio (horário, catálogo) são injetados em runtime pelo
  app (fica no app, não no template).

## Tools

```python
class GetWeatherInput(BaseModel):
    city: Literal["São Paulo", "Rio de Janeiro"]   # enum fechado > string livre

@tool("get_weather", args_schema=GetWeatherInput)
async def get_weather(city: str) -> dict:
    """Clima atual da cidade. Use quando o usuário perguntar sobre tempo/temperatura."""
```

- **Docstring + `Field(description)` = o prompt da tool.** Diga QUANDO usar e quando NÃO.
- Async (I/O com `http-client`/asyncpg); nada de `requests` bloqueante em handler async.
- Falha **esperada** (validação, não achou) → `return action_error("…")` (o modelo lê e se recupera);
  exceção só pra bug. Escrita feita → `action_confirmation("Agendado para …", **extras)`.
- Tool que só alimenta o raciocínio (busca, linhas cruas) devolve dado simples; o agente escreve a
  conclusão em texto. Envelope de card é opt-in (`frontend-chat.md`).
- Escopo de tenant na tool: leia `tenant_id`/`user_id` do `RunnableConfig` (`config["configurable"]`/
  `metadata`), NUNCA de argumento que o modelo preenche.
- Ação destrutiva/irreversível: confirmar com o usuário antes (o agente pergunta) ou separar "preparar"
  de "executar".

## Checkpointer e thread

`AsyncPostgresSaver` singleton (`checkpointer.py`: `init_checkpointer`/`get_checkpointer`/`close_checkpointer`
no lifespan). `thread_id = session_id` em `config["configurable"]`; estado do grafo persiste a cada passo.
WhatsApp: `thread_id = conversation.agent_thread_id or conversation.id` (1 thread por conversa). Tabelas
`checkpoints/checkpoint_writes/checkpoint_blobs` vêm da migration dbmate — nunca `setup()` em runtime.
`chat_history` = transcript renderizável na UI; checkpoint = estado do grafo; `agent_message_usage` = custo.

## Não-chat

Agente executado sem stream (job, webhook): `call_agent_async`/`execute_agent`
(`services/agents/executors.py`) — devolve resposta + metadata de custo. Passe `tenant_id`/`agent_id`
no config para o recorder.
