---
name: logging-setup
description: Bootstrap or audit the structlog + stdlib + orjson + QueueHandler logging stack in a Python/FastAPI/Granian backend. INVOKE ONLY for setup tasks — setting up logging in a new project, migrating print() to logger, fixing log rotation in Docker, configuring request_id correlation, ConsoleRenderer vs JSONRenderer pipeline, NDJSON serialization, dictConfig for Granian/uvicorn, banimento de print() via ruff T20. For DAILY logging usage (which level to pick, snake_case event names, kwargs not f-string) follow the `logs.md` rule directly — do not invoke this skill.
---

# logging-setup

Bootstrap one-shot do stack de logging padrão dos projetos. Stack fixo: **structlog + stdlib `logging` + orjson + QueueHandler/QueueListener**, NDJSON em prod, ConsoleRenderer em dev (TTY-aware), `request_id` via contextvar correlacionado com `X-Request-ID` do nginx.

Ler primeiro a rule global `~/.claude/rules/logs.md` (ou `.claude/rules/logs.md` do projeto) — ela é a fonte canônica do padrão. Esta skill é o **runbook de aplicação**.

## Quando usar este skill

- Projeto novo (FastAPI + Granian) que ainda usa `print()`, `logging.basicConfig` ou nada.
- Pedido para "padronizar logs" / "setup logging" / "structlog" / "JSON logs em produção".
- Migração de `print()` para logger estruturado.
- Adicionar rotação Docker (`json-file` com `max-size`/`max-file`).
- Bug de logger third-party (asyncpg, granian, uvicorn) saindo em formato diferente do app.

## Mental model

```
log.info("event", **ctx)
  ↓ structlog processors (caller-side, em ordem)
  merge_contextvars → add_log_level → add_logger_name
  → TimeStamper(iso, utc) → _add_service_context → _resolve_exc_info
  → StackInfoRenderer → [format_exc_info se JSON]
  → wrap_for_formatter
  ↓ stdlib LogRecord (msg = event_dict)
  ↓ root logger
  ↓ _RawQueueHandler.prepare → queue.put (NÃO chama getMessage)
  ↓ ────────── thread switch ──────────
  ↓ QueueListener thread
  ↓ StreamHandler com ProcessorFormatter
  ↓ remove_processors_meta + final renderer (JSON ou Console)
  ↓ stderr.write(bytes + "\n")
  ↓ Docker json-file driver (rotação)
```

Pontos não-óbvios:

- `_RawQueueHandler` é **mandatório**. Default `QueueHandler.prepare` chama `record.getMessage()` que coage o event_dict para str → `ProcessorFormatter` quebra com `'str' has no attribute 'copy'`.
- `_resolve_exc_info` é **mandatório**. `exc_info=True` no thread caller é resolvido por `sys.exc_info()`. No thread do listener, `sys.exc_info()` é `(None, None, None)` → traceback some silenciosamente.
- `format_exc_info` só entra no pipeline em modo JSON. ConsoleRenderer formata exceções nativamente e **emite UserWarning** se ver traceback pré-formatado.
- `setup_logging()` deve ser chamado no **top-level de `api/main.py`**, antes de `app = FastAPI(...)`. Granian/uvicorn importam o módulo → top-level executa antes de qualquer request → handlers configurados a tempo.

## Runbook de bootstrap (projeto novo)

Aplicar **na ordem** abaixo. Cada passo é idempotente.

### 1. Dependência

```bash
cd <projeto>/backend
uv add structlog
```

`orjson` deve já existir (parte da stack base do backend). Se não: `uv add orjson`.

### 2. Copiar `core/logging.py`

Conteúdo canônico em `references/logging.py`. Path destino: `<projeto>/backend/src/api/core/logging.py`.

Não inventar variações — esse arquivo foi validado em 4 projetos sob carga real. Mudanças exigem atualizar a rule global.

### 3. Copiar `LoggingMiddleware`

Conteúdo canônico em `references/logging_middleware.py`. Path destino: `<projeto>/backend/src/api/middlewares/logging_middleware.py`.

ASGI puro — NÃO usa `BaseHTTPMiddleware` (esse quebra streaming/SSE). Lê `X-Request-ID`, gera UUID4 se ausente, faz echo no header da resposta, loga 1 linha com `method/path/status/duration_ms/client_ip` no fim.

`SILENT_PATHS` por padrão: `/api/v1/health`, `/healthz`, `/api/v1/docs`, `/api/v1/redoc`, `/api/v1/openapi.json`, `/favicon.ico`. Em probes 200 não loga; em 4xx/5xx loga sempre (`level=warning`).

### 4. Editar `api/main.py`

```python
# Imports — adicionar:
from api.core.logging import get_logger, setup_logging, shutdown_logging
from api.middlewares.logging_middleware import LoggingMiddleware

# Antes de `app = FastAPI(...)`:
setup_logging()
log = get_logger(__name__)

# No lifespan:
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup_begin")
    # ... init pools, services ...
    yield
    # ... shutdown ...
    log.info("shutdown_complete")
    shutdown_logging()

# Após os outros middlewares (LoggingMiddleware é OUTERMOST = último add):
app.add_middleware(LoggingMiddleware)
```

Trocar `print()` no lifespan por `log.info("event", ...)` ou `log.exception(...)`.

### 5. Editar `backend/ruff.toml`

Adicionar `"T20"` em `extend-select` e usar **glob negativo** para escopar só em `src/**`:

```toml
extend-select = [
    # ...resto...
    "T20", # flake8-print — bans print() / pprint(). Use structlog (see logs.md).
]

[lint.per-file-ignores]
"tests/**/*.py" = [..., "T201"]
# T20 (print/pprint) só vale em src/**. Notebooks, pipelines, scripts usam livremente.
"!src/**/*.py" = ["T20"]
# Nosso módulo `logging.py` shadows o stdlib intencionalmente.
"src/api/core/logging.py" = ["A005"]
```

O glob negativo `"!src/**/*.py" = ["T20"]` ignora a categoria toda (T201 print + T203 pprint) em qualquer arquivo que NÃO esteja em `src/`. Mais limpo que listar paths individuais.

A005 isenta o `core/logging.py` — o nome do arquivo intencionalmente shadows o `logging` da stdlib (é wrapper do projeto). Imports internos usam paths absolutos qualificados.

### 6. Editar `compose.yaml` — logging assimétrico

NÃO aplicar logging block em todos os services. Postgres/nats/migrate raramente são consultados em incidente — basta `docker logs` quando necessário, e o default do Docker daemon (~10MB sem rotação) cobre.

Aplicar **apenas em**:

```yaml
services:
    backend:
        environment:
            SERVICE_NAME: <projeto>-backend
            APP_ENV: ${APP_ENV:-local}
            LOG_LEVEL: ${LOG_LEVEL:-INFO}
        # ... resto ...
        # Logs estruturados (NDJSON via structlog) — maior cota.
        logging:
            driver: json-file
            options:
                max-size: "100m"
                max-file: "10"
                compress: "true"

    cron-worker: # se existir
        environment:
            SERVICE_NAME: <projeto>-cron-worker
            APP_ENV: ${APP_ENV:-local}
            LOG_LEVEL: ${LOG_LEVEL:-INFO}
        # ...
        logging:
            driver: json-file
            options:
                max-size: "30m"
                max-file: "10"
                compress: "true"

    nginx: # se existir
        # ...
        # Access log JSON em alto volume.
        logging:
            driver: json-file
            options:
                max-size: "50m"
                max-file: "10"
                compress: "true"
```

Cota total: ~1-2 GB por host. Backend recebe a maior parte (rotas + erros + business events).

### 7. Migrar `print()` em `src/`

Rodar `uv run ruff check --select T201 src/`. Para cada hit:

| `print` original                                    | Migração                                                                 |
| --------------------------------------------------- | ------------------------------------------------------------------------ |
| `print(f"[ctx] msg {var}")` em fluxo normal         | `log.info("event_name_snake_case", var=var)`                             |
| `print(f"... ERROR ...{format_exc()}")` em `except` | `log.exception("event_name_failed")` — NUNCA passe `format_exc()` manual |
| `print(...)` controlado por flag de debug           | `log.debug("event_name", **ctx)`                                         |
| `print(..., flush=True)` ou `end=" "`               | `log.info(...)` normal — flush e end são hacks de TTY                    |
| Erro explícito com variável `err`                   | `log.error("event_name", error=repr(err))`                               |

`event` SEMPRE em snake_case, sem prefixo `[bracket]`, sem espaços. Variáveis interpoladas viram kwargs.

Se `from traceback import format_exc` ficar órfão depois da migração, remover do import.

### 8. Validação end-to-end

```bash
# Lint zerado
cd backend && uv run ruff check --select T201 src/   # → All checks passed!

# Smoke test (gera 1 linha NDJSON válida)
SERVICE_NAME=test APP_ENV=local LOG_LEVEL=INFO LOG_FORMAT=json \
uv run python -c "
import sys
sys.path.insert(0, 'src')
from api.core.logging import setup_logging, get_logger, bind_request_id, shutdown_logging
setup_logging()
log = get_logger('smoke')
bind_request_id('rid-test')
log.info('smoke_ok')
import time; time.sleep(0.05)
shutdown_logging()
" 2>&1 | jq

# Docker up + correlation test
cd .. && docker compose up -d --build backend
sleep 8
curl -s -H 'X-Request-ID: rid-correlation' http://127.0.0.1:8000/api/v1/<rota_real>
docker logs <projeto>-backend --since 5s 2>&1 | rg "rid-correlation" | jq

# Rotação
docker inspect <projeto>-backend --format '{{json .HostConfig.LogConfig}}' | jq
# Esperado: {"Type":"json-file","Config":{"compress":"true","max-file":"10","max-size":"100m"}}
```

## Auditoria de projeto existente

Quando o user pede "verifica se o logging do projeto X está OK", checar nesta ordem:

1. **`structlog` no pyproject.toml** (`grep "structlog" backend/pyproject.toml`).
2. **`backend/src/api/core/logging.py` existe e bate com `references/logging.py`** (`diff` quase zero).
3. **`LoggingMiddleware` está em `src/api/middlewares/logging_middleware.py`** e adicionado em `main.py` (`rg "app.add_middleware\(LoggingMiddleware\)" src/api/main.py`).
4. **`setup_logging()` chamado no top-level** de `main.py`, antes de `app = FastAPI(...)`.
5. **`shutdown_logging()`** no fim do lifespan.
6. **`SERVICE_NAME` e `APP_ENV`** no compose, no service `backend`.
7. **`logging:` block** no compose ao menos em `backend` (e nginx se existir).
8. **`T20` no ruff.toml** com glob negativo `"!src/**/*.py" = ["T201"]`.
9. **Zero `print()` em `src/`**: `cd backend && uv run ruff check --select T201 src/`.
10. **Smoke test passa** (passo 8 acima).

Se algum item falhar, aplicar o passo correspondente do runbook. Não refatorar código não relacionado.

## Anti-patterns a flagar

- `logging.basicConfig(...)` em código de produção → trocar por `setup_logging()`.
- `loguru` import → remover, migrar para structlog.
- `print()` em `src/` → migrar (lint pega via T20).
- File handler dentro do container (`logging.FileHandler('/var/log/...')`) → REMOVER. Saída sempre stdout/stderr; rotação via Docker driver.
- `OPT_INDENT_2` no orjson serializer → REMOVER. Quebra NDJSON.
- `BaseHTTPMiddleware` no LoggingMiddleware → REMOVER. Pure ASGI obrigatório (streaming/SSE).
- Chamar `setup_logging()` dentro do lifespan async → MOVER para top-level. Granian importa antes do lifespan; logs do startup ficam fora do pipeline.
- `log.error(f"... {exc}")` em except → trocar por `log.exception("event_failed")`. Mantém traceback.
- `f"... {var} ..."` no `event` do logger → ERRADO. Event = snake_case fixo, variável vai como kwarg.
- Duplicar logging block em todos os services do compose → remover de postgres/nats/migrate. Default do daemon basta.

## Reference files

- `references/logging.py` — módulo central canônico (copiar literal).
- `references/logging_middleware.py` — middleware ASGI canônico.

Atualizar esses references **toda vez** que `core/logging.py` ou `logging_middleware.py` do projeto de referência mudar — é fonte de verdade.
