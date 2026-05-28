---
name: python-config-bootstrap
description: Bootstrap e operação do padrão config env-aware Python/FastAPI — layout `config/app/{local,staging,prod}.yaml` versionado + `.env` (secrets) + `app.yaml` runtime (copy do env-específico) + `Settings` Pydantic com fail-fast no module load. Cobre também `config/docker/compose.{env}.yaml` overrides, shims `config/api.py`/`config/database.py`, regras de `${VAR}` substitution em `compose.yaml` base, e env vars `GRANIAN_*` consumidas pelo Dockerfile CMD. INVOCAR ANTES de — adicionar nova config env-aware (precisa editar OS 3 yamls + sub-model em Settings), adicionar nova secret (`.env.example` + `SecretStr` em Settings), criar `Settings` do zero em projeto novo, criar/alterar `compose.override.yaml`, bootstrap inicial (`cp config/app/local.yaml app.yaml`), tocar `compose.yaml` base com `${VAR}`, ou popular secondary Python process com seu próprio settings.py mínimo. NUNCA commit valor real de secret; NUNCA hardcode env-specific value em `compose.yaml` base (vai pro override).
---

# Python Config Bootstrap — yaml + .env + Pydantic Settings

Padrão canônico cross-projeto para configuração env-aware (`local` / `staging` / `prod`) sem feature flags em runtime. Source of truth: yaml versionado + secrets em `.env`. Settings Pydantic faz fail-fast no module load.

## Layout completo

```
projeto/
├── .env                           # SECRETS (gitignored, manual provisioning)
├── .env.example                   # Template (versionado, valores vazios)
├── app.yaml                       # Runtime (gitignored, copy do env-específico)
├── compose.yaml                   # Base Docker (versionado)
├── compose.override.yaml          # Runtime override (gitignored, copy)
└── config/
    ├── settings.py                # Pydantic Settings (single import surface)
    ├── api.py                     # SHIM legado (UPPER_CASE aliases)
    ├── database.py                # SHIM legado (UPPER_CASE aliases)
    ├── tools.py                   # getenv_or_raise_exception helpers
    ├── app/
    │   ├── local.yaml             # versionado
    │   ├── staging.yaml           # versionado
    │   └── prod.yaml              # versionado
    └── docker/
        ├── compose.local.yaml     # versionado
        ├── compose.staging.yaml   # versionado
        └── compose.prod.yaml      # versionado
```

## Tabela de decisão — onde mora cada coisa

| Categoria                    | Onde vive                                         | Versionado | Lido por                                               |
| ---------------------------- | ------------------------------------------------- | ---------- | ------------------------------------------------------ |
| Secrets                      | `.env` (root)                                     | Não        | `getenv_or_raise_exception` em `config/tools.py`       |
| Config app (env-aware)       | `config/app/{local,staging,prod}.yaml`            | Sim        | `Settings` (Pydantic + PyYAML) em `config/settings.py` |
| Runtime local                | `app.yaml` (root, copy do pai)                    | Não        | `Settings()` no module load (fail-fast)                |
| Docker overrides (env-aware) | `config/docker/compose.{env}.yaml`                | Sim        | `cp` para `compose.override.yaml`                      |
| Compose base                 | `compose.yaml` (root)                             | Sim        | `docker compose up` (junto com override)               |

## Bootstrap por ambiente

```bash
# Local development
cp config/app/local.yaml app.yaml
cp config/docker/compose.local.yaml compose.override.yaml
# .env: provisionado manualmente (cofre / 1Password / scp)

# Staging
cp config/app/staging.yaml app.yaml
cp config/docker/compose.staging.yaml compose.override.yaml

# Production
cp config/app/prod.yaml app.yaml
cp config/docker/compose.prod.yaml compose.override.yaml
```

Esses `cp` são as únicas operações env-aware no host. Container runtime lê só `app.yaml` + `.env`, sem conhecer o nome do env.

## `config/settings.py` — fail-fast pattern

```python
import pathlib
import yaml
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings


class JwtConfig(BaseModel):
    issuer: str
    audience: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    leeway_seconds: int = 10


class CookiesConfig(BaseModel):
    secure: bool


class WhatsappConfig(BaseModel):
    public_base_url: str


class ViteConfig(BaseModel):
    meta_app_id: str
    meta_es_config_id: str
    meta_graph_api_version: str = "v25.0"


class Settings(BaseSettings):
    # From app.yaml
    jwt: JwtConfig
    cookies: CookiesConfig
    whatsapp: WhatsappConfig
    vite: ViteConfig

    # From .env
    jwt_secret_key: SecretStr
    valkey_password: SecretStr
    google_oauth_client_secret: SecretStr
    meta_app_secret: SecretStr
    whatsapp_webhook_verify_token: SecretStr

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def _load() -> Settings:
    yaml_path = pathlib.Path(__file__).parent.parent / "app.yaml"
    if not yaml_path.exists():
        raise RuntimeError(
            f"app.yaml not found at {yaml_path}. "
            f"Run: cp config/app/local.yaml app.yaml"
        )
    yaml_data = yaml.safe_load(yaml_path.read_text())
    return Settings(**yaml_data)


# Import-time fail-fast: app explodes on startup if config is bad.
settings = _load()
```

Critical:

- `settings = _load()` roda **no import** — não em runtime. App não sobe sem `app.yaml` válido + secrets obrigatórias no `.env`.
- Cada secret é `SecretStr` (logging não vaza). Acesso: `settings.jwt_secret_key.get_secret_value()`.
- Sub-models (`JwtConfig`, `CookiesConfig`, etc.) — um por seção do yaml. NUNCA flat dict.

## Como adicionar NOVA config env-aware (3 passos)

1. **Edita OS 3 yamls** (`config/app/{local,staging,prod}.yaml`), mesmo que o valor seja igual em 2 deles. Manter os 3 simétricos é invariante — facilita diff entre envs.

```yaml
# config/app/local.yaml
new_feature:
  timeout_seconds: 5
  enabled: true

# config/app/staging.yaml
new_feature:
  timeout_seconds: 10
  enabled: true

# config/app/prod.yaml
new_feature:
  timeout_seconds: 30
  enabled: true
```

2. **Adiciona sub-model em `Settings`**:

```python
class NewFeatureConfig(BaseModel):
    timeout_seconds: int
    enabled: bool

class Settings(BaseSettings):
    ...
    new_feature: NewFeatureConfig
```

3. **`cp config/app/local.yaml app.yaml`** novamente em dev (ou deixa o entrypoint do container fazer no deploy).

## Como adicionar NOVA secret (2 passos)

1. **`.env.example`** (versionado, valor vazio):

```bash
NEW_API_KEY=
```

2. **Field `SecretStr` em `Settings`**:

```python
class Settings(BaseSettings):
    ...
    new_api_key: SecretStr
```

Instrua o user a popular `.env` local manualmente. **NUNCA** commit valor real.

## Shims `config/api.py`, `config/database.py`

São camada de compatibilidade legada — expõem `UPPER_CASE` aliases para callsites antigos:

```python
# config/database.py
from config.settings import settings

POSTGRES_HOST = settings.postgres.host
POSTGRES_PORT = settings.postgres.port
POSTGRES_DB = settings.postgres.db
DATABASE_URL = settings.postgres.url
```

Regra: **NÃO introduza lógica nova nos shims.** Sempre escreva em `settings.*` (pydantic-validated). Shim só renomeia.

## `compose.yaml` base — regras de `${VAR}`

`compose.yaml` é o esqueleto compartilhado. `${VAR}` substitution **APENAS para secrets vindas do `.env`**:

```yaml
# compose.yaml (base, versionado)
services:
  postgres:
    image: postgres:18
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}   # ← OK, vem do .env
      # POSTGRES_DB: ${POSTGRES_DB}              ← PROIBIDO, é env-aware
    volumes:
      - postgres_data:/var/lib/postgresql/data

  api:
    build: ./backend
    environment:
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}         # ← OK, vem do .env
```

Configs env-aware (`POSTGRES_DB`, `VITE_*`, `GRANIAN_WORKERS_MAX_RSS`) ficam **literais** em `compose.{env}.yaml > environment:`:

```yaml
# config/docker/compose.local.yaml (versionado)
services:
  postgres:
    environment:
      POSTGRES_DB: kailos_local

  api:
    environment:
      GRANIAN_WORKERS_MAX_RSS: 512
      GRANIAN_WORKERS: 1
      LOG_LEVEL: DEBUG
```

```yaml
# config/docker/compose.prod.yaml
services:
  postgres:
    environment:
      POSTGRES_DB: kailos_prod

  api:
    environment:
      GRANIAN_WORKERS_MAX_RSS: 2048
      GRANIAN_WORKERS: 4
      LOG_LEVEL: INFO
```

## Granian env vars

`GRANIAN_*` env vars são consumidas pelo Dockerfile CMD via shell:

```dockerfile
CMD ["sh", "-c", "granian \
  --interface asgi \
  --host 0.0.0.0 \
  --port 8000 \
  --workers ${GRANIAN_WORKERS:-1} \
  --workers-max-rss ${GRANIAN_WORKERS_MAX_RSS:-512} \
  src.api.main:app"]
```

Constantes (`--interface asgi`, `--host 0.0.0.0`) ficam no `compose.yaml` base via Dockerfile. O que varia por env (`GRANIAN_WORKERS_MAX_RSS`, `GRANIAN_WORKERS`) vai no override.

## Secondary Python processes

Cron-worker, NATS subscriber, batch processor que compartilham o mesmo deploy:

- Montam o mesmo `app.yaml` via volume Docker (`./app.yaml:/app/app.yaml:ro`).
- Têm seu próprio `settings.py` mínimo — pode ser sem Pydantic se o subset for trivial:

```python
# worker/settings.py
import pathlib
import yaml

_data = yaml.safe_load(
    (pathlib.Path(__file__).parent.parent / "app.yaml").read_text()
)
NATS_URL = _data["nats"]["url"]
WORKER_CONCURRENCY = _data["worker"]["concurrency"]
```

Sem dup de Pydantic se a leveza justificar. Mas se há validação não-trivial, usa Pydantic igual ao app principal.

## Don'ts

- **NUNCA** hardcode valor env-aware em `compose.yaml` base — vai pro override.
- **NUNCA** `${ENV_VAR}` em `compose.yaml` base para coisa não-secret.
- **NUNCA** introduza lógica nova em `config/api.py`/`config/database.py` — são shims, só renomeiam de `settings.*`.
- **NUNCA** lê env var direto em business code (`os.getenv(...)`). Sempre via `settings`.
- **NUNCA** commit valor real de secret. `.env.example` tem valores vazios; `.env` é gitignored.
- **NUNCA** acesse `.env` de Python além de `tools.py`/`settings.py`. Layer único de boundary.
- **NUNCA** assume que `app.yaml` existe — `_load()` checa explicitamente e levanta com mensagem útil.
