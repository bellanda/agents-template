# Backup diário do Postgres no Backblaze B2 — serviço `pg-backup`

Padrão da frota desde 2026-10-14. O código está no Git e no OneDrive, e mídia/documentos estão no B2. Na VPS,
o único dado que não se regenera é o **Postgres**, e este serviço cobre esse buraco.
Canônico: `~/code/kailos/config/backup/{Dockerfile,pg_backup.sh}` + serviço `pg-backup` em
`config/docker/compose.prod.yaml`. Todo app copia os mesmos dois arquivos **sem alteração**; o que muda por
app vive no compose.

## Decisões do usuário (2026-10-14)

- **Destino:** o **mesmo bucket privado do app** (`<app>-private`), acessado com a **mesma chave privada** que
  o app já usa. Não existe bucket nem chave nova. Uma chave separada não protegeria nada, porque ficaria no
  mesmo `.env` das outras.
- **Pasta na RAIZ do bucket**, fora do `b2_key_prefix` (`prod/` / `staging/`): `backups/postgres/`. O código da
  app nunca grava nem apaga em `backups/`.
- **Retenção: 7 dias + 4 semanais.** Começou como "1 diário + 4 semanais", e o usuário ampliou no mesmo dia: com 1
  diário, uma corrupção percebida dias depois só voltava até o domingo. O objetivo é conter danos (servidor perdido, migration que
  corrompeu, invasão), não recuperar algo que o usuário apagou semanas atrás.
- **Backup antes de todo deploy** (`docker compose run --rm pg-backup now`). O deploy roda migrations, e esse backup é a
  cópia imediatamente anterior a elas. Ver `global/agent-behavior.md` → Deploy.
- **Dump lógico (`pg_dump -Fc`) até a casa dos TB.** Os apps ficam ociosos das 22h às 06h. Migrar para
  backup físico + WAL (PITR, `pg_basebackup --incremental`; o `summarize_wal = on` já está no `prod.conf`)
  **só quando o dump ou o restore não couber mais nessa janela**. Não há limite fixo de GB.

## Layout no bucket

```
<app>-private/
  prod/…                                        ← uploads da app (b2_key_prefix)
  backups/postgres/daily/<app>-<YYYY-MM-DDTHHMM>.dump    ← todos os arquivos dos 7 dias mais recentes
  backups/postgres/weekly/<app>-<YYYY-MM-DD>.dump        ← cópia de domingo, mantém 4
```

Os nomes embutem um timestamp ISO, então a ordem alfabética é a ordem cronológica, e a retenção depende disso.
A retenção diária conta **dias distintos**, não arquivos: o backup antes do deploy também cai em `daily/`, e
3 deploys num dia não podem empurrar 3 dias para fora.

## Como funciona (`pg_backup.sh`)

| Subcomando | O que faz |
| --- | --- |
| `run` (default) | Loop de 60s. Faz 1 backup por dia local, a partir de `BACKUP_HOUR_LOCAL` (3 = 03:00 `America/Sao_Paulo`). A checagem é `>=`, então um restart depois das 03h ainda recupera o dia perdido. Falha → nova tentativa em 15 min. |
| `now` | Faz 1 backup imediato e sai com 0/1. É o modo manual e o do "backup antes do deploy". |
| `healthcheck` | Fica unhealthy se o último **sucesso** tiver mais de 26h. Há tolerância de 26h desde o start do container, para o deploy recém-feito não aparecer unhealthy. |
| `select-expired N` | Recebe nomes no stdin e devolve os que estão fora dos N dias mais recentes. É a lógica de retenção, isolada para teste. |

Passos de cada backup (1 linha JSON de log por passo):
1. `pg_dump -Fc --compress=zstd` pelo **socket direto** (`pgsocket`, nunca pgbouncer em transaction mode),
   para um arquivo temporário no volume `pgbackup-tmp`.
2. `pg_restore --list`: valida que o arquivo é um dump íntegro.
3. Cancela upload grande inacabado sob `backups/` (sobra de execução que caiu; parte guardada é cobrada).
4. `b2 file upload` em `daily/`. O CLI faz o large file/multipart sozinho acima do limite e confere o SHA1.
   Depois, `b2 file info` confirma o tamanho exato.
5. Domingo: a mesma coisa em `weekly/`, seguida da retenção semanal.
6. Retenção diária, **só depois** do upload confirmado, e só se o arquivo novo aparece na listagem. O bucket é
   versionado, então ela usa `b2 rm --versions` (todas as versões; senão o arquivo continua guardado e cobrado).
7. Grava o heartbeat e a data do último sucesso. Qualquer falha antes disso faz não apagar nada.

Por que a ferramenta é o `b2` CLI (binário oficial, versão fixa com sha256, interface congelada `b2v4`) e não
boto/S3: ele fala a API nativa e trata arquivo grande sozinho (5 GB por PUT, 10 TB por arquivo). Isso evita a
armadilha do checksum CRC32 `aws-chunked` do boto ≥1.36, que o B2 rejeita (ver `uploads-storage` §9b).
Por que `FROM postgres:18.4-trixie`: o `pg_dump` tem de ter a mesma major do servidor.

## Serviço no compose (só `config/docker/compose.prod.yaml`)

```yaml
  pg-backup:
    container_name: <app>-pg-backup
    build: { context: ../backup }
    environment:
      BACKUP_APP: <app>
      BACKUP_HOUR_LOCAL: "3"
      TZ: America/Sao_Paulo
      POSTGRES_USER: <app>
      POSTGRES_DB: <app>
      B2_PRIVATE_BUCKET: <storage.b2_private_bucket do prod.yaml>
      B2_PRIVATE_KEY_ID: "<storage.b2_private_key_id do prod.yaml>"
      HOME: /backup
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}      # só estes 2 segredos, sem env_file
      B2_PRIVATE_APP_KEY: ${B2_PRIVATE_APP_KEY}
    volumes: [pgsocket:/var/run/postgresql, pgbackup-tmp:/backup]
    tmpfs: [/tmp:exec]          # o binário b2 (staticx) se extrai e executa em /tmp; tmpfs é noexec por padrão
    read_only: true
    security_opt: [no-new-privileges:true]
    cap_drop: [ALL]
    networks: [internal]        # precisa de saída para a internet (B2) — bridge comum, não `internal: true`
    depends_on: { postgres: { condition: service_healthy } }
    healthcheck: { test: ["CMD", "/usr/local/bin/pg_backup.sh", "healthcheck"], interval: 5m, timeout: 10s, retries: 1, start_period: 30s }
    restart: unless-stopped
volumes:
  pgbackup-tmp:
```

O serviço **nunca** entra em local/test: dev nunca grava no B2.

## Operação

```bash
docker compose run --rm pg-backup now                      # backup manual (e antes de todo deploy)
docker compose logs --tail=50 pg-backup                    # 1 JSON por passo; "event":"done" = sucesso
docker compose ps pg-backup                                # healthy = sucesso nas últimas 26h
```

## Restore (runbook)

Rode na VPS, com o stack no ar, **sem tocar no banco de produção** até a conferência terminar:

```bash
cd /opt/<app>
# 1. Escolher o arquivo (daily/ ou weekly/)
docker compose run --rm --entrypoint b2 pg-backup ls --long -r "b2://<app>-private/backups/postgres/"
# 2. Baixar para o volume do backup
docker compose run --rm --entrypoint b2 pg-backup file download \
  "b2://<app>-private/backups/postgres/daily/<arquivo>.dump" /backup/restore.dump
# 3. Restaurar num banco NOVO e conferir
docker compose exec -T postgres createdb -U <app> <app>_restore
docker compose run --rm --entrypoint pg_restore -e PGPASSWORD="$POSTGRES_PASSWORD" pg-backup \
  --no-owner -h /var/run/postgresql -U <app> -d <app>_restore /backup/restore.dump
docker compose exec -T postgres psql -U <app> -d <app>_restore -c "SELECT count(*) FROM organizations;"
# 4. Trocar: parar a app (backend/cron), renomear os bancos, subir de novo
#    ALTER DATABASE <app> RENAME TO <app>_old; ALTER DATABASE <app>_restore RENAME TO <app>;
# 5. Apagar /backup/restore.dump (e <app>_old quando tiver certeza)
```

Validado em 2026-10-14: dump de 50 mil linhas → restore num banco novo, contagens e md5 idênticos.

## Pitfalls

- **NUNCA** `pg_dump` pelo pgbouncer: em transaction mode a sessão longa prende uma conexão do pool e quebra o
  snapshot. Use sempre o socket direto (`pgsocket`).
- **NUNCA** apagar o backup antigo antes de confirmar o novo (tamanho + presença na listagem). O script já
  garante isso; não "otimize".
- **NUNCA** `docker compose down -v` em prod: apaga o volume do banco. O backup não substitui esse cuidado.
- `set -e` é ignorado em função chamada à esquerda de `||`. Por isso o backup roda num processo filho
  (`"$0" __backup`); sem isso, um passo que falha seguiria até a retenção.
- O bucket é versionado: `b2 rm` sem `--versions` só esconde, e a versão segue cobrada.
- O tmpfs `/tmp` precisa de `exec`, porque o binário `b2` se autoextrai ali ("Failed to execv() /tmp/staticx-*").
- O trap `RETURN` do bash é global depois de setado. Ele tem de se auto-resetar (`trap - RETURN` dentro dele);
  senão dispara de novo quando o `main()` retorna, fora da função, com a variável não definida, e o `set -u`
  derruba um backup que já tinha dado certo. Achado no 1º backup real (2026-10-14); o dry run não pegava.
- O `b2 file info` (v4) devolve o tamanho em `.size`, não `.contentLength`.
