---
paths:
  - "**/*.py"
---

# Logging

Stack já bootstrapado nos projetos. Para configurar do zero ou auditar setup, invoque skill `logging-setup`.

## Stack (fixo, não negociável)

structlog → stdlib `logging` → QueueHandler/QueueListener → stderr →
JSONRenderer com orjson em prod (NDJSON) | ConsoleRenderer em dev (TTY-aware) →
Docker `json-file` driver (rotação, compressão).

## Como usar (todo arquivo Python)

```python
import structlog
log = structlog.get_logger(__name__)
```

## Regras

- `print()` PROIBIDO. Lint `T20` falha o build.
- Event = `snake_case_verb_or_noun`. Context = kwargs. NUNCA f-string a mensagem.
  - ✅ `log.info("user_login", user_id=42, method="oauth")`
  - ❌ `log.info(f"user {uid} logged in")`
- `log.exception("operation_failed")` dentro de `except`. NUNCA `log.error(str(e))` — perde traceback.
- Sem file handlers no container. stdout/stderr only. Docker driver rotaciona.
- `request_id` é contextvar populada pelo `LoggingMiddleware`. Toda linha herda automático.

## Quando logar (volume = sinal, não narração)

| Nível     | Quando                                                                                                                       |
| --------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `INFO`    | 1 linha por request HTTP (middleware), business event (`user_login`, `order_paid`), call externa start/end, worker lifecycle |
| `WARNING` | HTTP 4xx/5xx, rate limit hit, condição recuperável inesperada                                                                |
| `ERROR`   | unhandled exception (sempre via `log.exception`), call externa que falhou                                                    |
| `DEBUG`   | passos internos, iteração de loop. Oculto em prod (`LOG_LEVEL=INFO`)                                                         |

Silence noise paths no middleware: `/health`, `/docs`, `/openapi.json`, `/favicon.ico`.

NUNCA logar: secrets, tokens, full request body, PII sem redaction explícita.

> Regra prática: se você não consegue articular como essa linha vai ajudar num incidente
> 3 AM, é DEBUG ou apaga.
