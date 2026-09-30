# One-shot e saída estruturada

> Reference do gate `ai-agents`. Canônico: `backend/src/api/core/agents/llm.py` (docstring do módulo
> é a spec). Use quando NÃO há conversa/tools/stream: código chama o modelo e lê a resposta.

## Quando usar

| Quero | Função | Retorno |
| --- | --- | --- |
| Texto livre (resumo, reescrita, descrição) | `complete(prompt, usage=…)` | `LlmResult` (`.text`, `.cost_usd`, `.cost_is_real`, `.message`) |
| Objeto que código consome (extração, roteamento, score) | `complete_structured(prompt, Schema, usage=…)` | `StructuredResult` (`.value` = instância Pydantic, `.raw` = `LlmResult`) |
| N passos fixos encadeados | vários `complete*` num service/job | — NÃO é agente |

```python
from api.core.agents.llm import UsageContext, complete, complete_structured

ctx = UsageContext(thread_id=f"doc:{doc_id}", agent_id="doc-summary", tenant_id=org_id)
summary = (await complete(f"Resuma em 3 linhas:\n\n{text}", usage=ctx, max_tokens=300)).text

class Lead(BaseModel):
    name: str | None
    intent: Literal["buy", "sell", "other"]

lead = (await complete_structured(message_text, Lead, usage=ctx)).value
```

## Regras

- **`usage` é keyword obrigatório** (aceita `None`, mas `None` = chamada invisível a custo/teto — só em
  script descartável). `agent_id` estável por PROPÓSITO (`"lead-scoring"`), `thread_id` sintético fora de
  chat (`f"job:{job_id}"`). Sem `thread_id`+`agent_id` o `usage_recorder` descarta a linha em silêncio.
- **Schema pequeno e plano**: `Literal`/`Enum` em vez de string livre; `| None` explícito quando o dado pode
  faltar (senão o modelo inventa). Descrições de campo (`Field(description=…)`) são prompt.
- `complete_structured` usa `method="function_calling"` (todo upstream do `provider_order` serve tool
  calling; `json_schema` estrito varia) e desliga reasoning por default. Decisão com julgamento pesado:
  `reasoning=True, reasoning_effort="high"` via overrides.
- **Parse falhou → `ValueError`.** Decida no caller (retry/fallback/marcar "revisão manual"); nunca
  engula nem devolva objeto parcial.
- `tools=[…]` em `complete` só FAZ O BIND: você executa os `tool_calls`. Se precisa de loop → agente.
- Overrides (`max_tokens`, `temperature`, `system=`) vão pro `init_model`. Modelo = `DEFAULT_MODEL` (GLM
  5.3 Flash); não passe outro.
- Retry/concorrência já embutidos (`with_llm_retry`: `CapacityLimiter(settings.agents.max_concurrent_llm)`,
  backoff com jitter, só 408/409/425/429/5xx/timeout). Fan-out de N chamadas: `anyio` task group (skill
  `anyio-concurrency`) — o limiter do processo protege o provedor.
- Crédito de teto: use `result.cost_usd` assim que a chamada volta (real quando `cost_is_real`).
- Prompt: estático primeiro, dado variável depois (prefix cache — `usage-cost.md`). Conteúdo de usuário
  dentro do prompt = dado, não instrução: delimite (`<documento>…</documento>`).

## Pipeline (vários passos) — como montar

```
extrair (complete_structured) → decidir em CÓDIGO (if/tabela) → agir (service) → opcional redigir (complete)
```

Cada passo com seu `agent_id` (`"lead-extract"`, `"lead-reply"`) → custo por etapa consultável. Só vire
agente se o modelo precisar escolher a sequência sozinho.
