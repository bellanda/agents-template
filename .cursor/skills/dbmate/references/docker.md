# dbmate + Docker

Padrões para integrar dbmate em ambiente containerizado. A regra é simples: **migration roda antes do app, e falha de migration aborta o boot.**

## 1. Princípio fundamental

```
[DB up] → [DB healthy] → [migrate roda e termina] → [app sobe]
                              ↑
                  se falhar aqui, app NÃO sobe
```

Em todos os padrões abaixo, a migration é uma etapa **bloqueante e separada** do start do app — nunca dentro do entrypoint do app. Razões:

- Múltiplas réplicas do app não competem para aplicar migration (race condition).
- Erro de migration é visível e isolado, não enterrado em log do app.
- Permite reaplicar/reverter sem reiniciar app.

## 2. Dev: docker-compose

Padrão recomendado para desenvolvimento local. Três serviços: `db`, `migrate`, `app`.

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: myapp
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d myapp"]
      interval: 2s
      timeout: 5s
      retries: 15

  migrate:
    image: ghcr.io/amacneil/dbmate:latest
    command: ["--wait", "up"]
    environment:
      DATABASE_URL: postgres://postgres:dev@db:5432/myapp?sslmode=disable
    volumes:
      - ./db:/db
    depends_on:
      db:
        condition: service_healthy

  app:
    build: .
    environment:
      DATABASE_URL: postgres://postgres:dev@db:5432/myapp?sslmode=disable
    ports:
      - "8000:8000"
    depends_on:
      migrate:
        condition: service_completed_successfully
    volumes:
      - ./:/app

volumes:
  pgdata:
```

### Como funciona

1. `db` sobe primeiro com healthcheck.
2. `migrate` espera `db` ficar `healthy` (`condition: service_healthy`).
3. `migrate` roda `dbmate --wait up` e termina (containers do dbmate são one-shot).
4. `app` espera `migrate` terminar com sucesso (`condition: service_completed_successfully`).
5. Se migrate falhar, app **não sobe**.

### Ponto crítico — volume

O serviço `migrate` precisa de:
- `./db` montado em `/db` (default que dbmate procura).

Se suas migrations estão em outro caminho, ajuste com `-d`:

```yaml
command: ["-d", "/migrations", "--wait", "up"]
volumes:
  - ./database/migrations:/migrations
```

### Comandos úteis no fluxo dev

```bash
# Subir tudo (DB + migrate + app)
docker compose up

# Só rodar migration (DB já existe)
docker compose run --rm migrate

# Criar nova migration
docker compose run --rm migrate new add_phone_to_users

# Status
docker compose run --rm migrate status

# Rollback
docker compose run --rm migrate rollback

# Resetar DB do zero
docker compose down -v && docker compose up
```

### Alternativa — dbmate local em vez de container

Se sua equipe já tem `dbmate` instalado localmente (`brew install dbmate` / `npm install -g dbmate`), pode pular o serviço `migrate` no compose e rodar direto do host:

```bash
# .env aponta para localhost:5432
dbmate up
```

Vantagem: comandos mais rápidos, sem overhead de container. Desvantagem: cada dev precisa instalar dbmate. **Recomendação:** suporte os dois — `make migrate` chama o `dbmate` local se existir, senão cai para `docker compose run --rm migrate`.

## 3. Prod / CI: migration como etapa do pipeline

Em produção, **não** suba o serviço `migrate` junto com o app. Migration é etapa do pipeline de deploy, antes do rollout do app.

### Padrão CI (GitHub Actions, GitLab CI, etc.)

```yaml
# .github/workflows/deploy.yml (esqueleto)
- name: Run migrations
  run: |
    docker run --rm \
      -v ${{ github.workspace }}/db:/db \
      -e DATABASE_URL="${{ secrets.DATABASE_URL }}" \
      ghcr.io/amacneil/dbmate:latest \
      --wait up

- name: Deploy app
  if: success()  # só faz deploy se migration passou
  run: ./deploy.sh
```

### Padrão Kubernetes — init container ou Job

**Opção A: Job dedicado (preferida).** Roda uma vez por deploy, separado do Deployment do app:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: migrate-{{ deploy_id }}
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: dbmate
        image: ghcr.io/amacneil/dbmate:latest
        args: ["--wait", "up"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: url
        volumeMounts:
        - name: migrations
          mountPath: /db
      volumes:
      - name: migrations
        configMap:
          name: db-migrations
```

Pipeline aplica o Job e espera ele completar antes de fazer rollout do Deployment.

**Opção B: initContainer no Deployment.** Cada pod do app roda migration antes de subir. **Não recomendado** — múltiplas réplicas competem; dbmate tem lock implícito via transação, mas há overhead e logs duplicados.

### Padrão CI/CD com ECS, Cloud Run, etc.

A lógica é idêntica:

1. Pipeline roda step "migrate" (em container ou via binary baixado).
2. Se passar, faz deploy/rollout do app.
3. Se falhar, aborta deploy e alerta.

## 4. Embedando migrations na imagem

Em prod, prefira **bundlar** as migrations dentro da imagem do migrator (em vez de montar volume). Garante que migrations versionadas no commit `X` sejam aplicadas na deploy `X`.

```dockerfile
# Dockerfile.migrate
FROM ghcr.io/amacneil/dbmate:latest
COPY db/migrations /db/migrations
COPY db/schema.sql /db/schema.sql
```

```bash
docker build -f Dockerfile.migrate -t myapp-migrate:${COMMIT_SHA} .
docker run --rm -e DATABASE_URL=... myapp-migrate:${COMMIT_SHA} --wait up
```

## 5. Multi-stage build com binary do dbmate

Se você quer **uma imagem só** que tem app + dbmate (não recomendado mas às vezes útil para tools/admin containers):

```dockerfile
FROM ghcr.io/amacneil/dbmate:latest AS dbmate

FROM python:3.13-slim AS app
COPY --from=dbmate /usr/local/bin/dbmate /usr/local/bin/dbmate
# ... resto do build do app
```

Agora o container do app pode rodar `dbmate` diretamente. Útil para shell de admin (`docker exec -it app dbmate status`), mas **não** chame dbmate no entrypoint do app — mantém migration como etapa separada.

## 6. Comandos de operação

### Healthcheck antes de migrate

`dbmate --wait up` já faz isso, mas se precisar sequenciar manualmente em script:

```bash
dbmate wait --wait-timeout=30s && dbmate up
```

### Verificar migrations pendentes em CI (sem aplicar)

```bash
dbmate status --exit-code --quiet
# exit 0 = tudo aplicado
# exit non-zero = há pendentes
```

Útil para gate em PR: "PR não pode mergear se houver migration pendente que não foi aplicada em staging".

### Reset completo em CI de teste

```bash
dbmate -e TEST_DATABASE_URL drop
dbmate -e TEST_DATABASE_URL create
dbmate -e TEST_DATABASE_URL --no-dump-schema load
```

`load` é muito mais rápido que aplicar centenas de migrations sequencialmente.

## 7. .env vs secrets

**Dev (compose):** `.env` na raiz, dbmate lê automaticamente.

**Prod:** `DATABASE_URL` vem de secret manager (AWS Secrets, Vault, K8s Secret, env do runner CI). **Nunca** commite `.env` com credenciais reais. `.gitignore`:

```
.env
.env.local
.env.*.local
```

Mantenha `.env.example` commitado com placeholders:

```env
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME?sslmode=disable
```

## 8. Resumo das decisões padrão

| Decisão | Padrão | Quando mudar |
|---|---|---|
| Migrate como serviço separado no compose | ✅ Sim | Quase nunca |
| Migrate dentro do entrypoint do app | ❌ Não | Nunca, em prod |
| Migration como Job/Step de pipeline em prod | ✅ Sim | — |
| initContainer em vez de Job | ❌ Não | Apenas se infra exigir |
| Bundle de migrations na imagem em prod | ✅ Sim | — |
| Volume montado para migrations em prod | ❌ Não | Só em dev |
| `dbmate dump` em CI/prod | ❌ Não | Dump é dev-only; commitar manualmente |
