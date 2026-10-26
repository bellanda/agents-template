# Backup diário do Postgres no Backblaze B2 — serviço `pg-backup`

Padrão da frota desde 2026-10-14. O código está no Git e no OneDrive, e mídia/documentos estão no B2. Na VPS,
o único dado que não se regenera é o **Postgres**, e este serviço cobre esse buraco. O `.env` NÃO vai para o B2 (decisão
2026-10-26, depois de cogitar subi-lo cifrado junto dos dumps): o local é copiado de hora em hora para
`OneDrive/Data (Git Ignored)/<app>/.env` pelo `~/scripts/backup.py`, e o de prod tem cópia manual em
`.../<app>/.env.prod` sempre que muda (ver `global/agent-behavior.md` → Deploy).
Canônico: `~/code/kailos/config/backup/{Dockerfile,pg_backup.sh}` + serviço `pg-backup` em
`config/docker/compose.prod.yaml`. Todo app copia os mesmos dois arquivos **sem alteração**; o que muda por
app vive no compose.

## Decisões do usuário (2026-10-14)

- **Destino:** o **mesmo bucket privado do app** (`<app>-private`), acessado com a **mesma chave privada** que
  o app já usa. Não existe bucket nem chave nova. Uma chave separada não protegeria nada, porque ficaria no
  mesmo `.env` das outras.
- **Pasta na RAIZ do bucket**, fora do `b2_key_prefix` (`prod/` / `staging/`): `backups/postgres/`. O código da
  app nunca grava nem apaga em `backups/`.
- **Retenção: 3 dias + 2 semanais + 1 mensal + o último pré-deploy = no máximo 7 dumps por app** (decisão do
  usuário 2026-10-26: "nunca fica mais que isso", para o bucket não crescer com o tempo; ele pediu "6 no total", a
  soma das partes dá 7 e ele confirmou as partes). Histórico: 2026-10-14 começou "1 diário + 4 semanais", ampliado
  no mesmo dia para "7 dias + 4 semanais". O objetivo é conter danos (servidor perdido, migration que corrompeu,
  invasão), não recuperar algo que o usuário apagou semanas atrás.
- **Backup antes de todo deploy** (`docker compose run --rm pg-backup now`). O deploy roda migrations, e esse backup é a
  cópia imediatamente anterior a elas. Ver `global/agent-behavior.md` → Deploy.
- **Dump lógico (`pg_dump -Fc`) até a casa dos TB.** Os apps ficam ociosos das 22h às 06h. Migrar para
  backup físico + WAL (PITR, `pg_basebackup --incremental`; o `summarize_wal = on` já está no `prod.conf`)
  **só quando o dump ou o restore não couber mais nessa janela**. Não há limite fixo de GB.

## Layout no bucket

```
<app>-private/
  prod/…                                        ← uploads da app (b2_key_prefix)
  backups/postgres/daily/<app>-<YYYY-MM-DDTHHMM>.dump      ← backup das 03:00, 1 por dia, 3 dias
  backups/postgres/weekly/<app>-<YYYY-MM-DD>.dump          ← cópia de domingo, mantém 2
  backups/postgres/monthly/<app>-<YYYY-MM-DD>.dump         ← 1º backup agendado do mês, SÓ o último
  backups/postgres/predeploy/<app>-<YYYY-MM-DDTHHMM>.dump  ← `now` antes do deploy, SÓ o último
```

Os nomes embutem um timestamp ISO, então a ordem alfabética é a ordem cronológica, e a retenção depende disso.
A retenção guarda **o arquivo mais novo de cada um dos N dias mais recentes** (`daily/` N=3, `weekly/` N=2,
`monthly/` e `predeploy/` N=1 → só o último). A cópia mensal sai no **primeiro backup agendado de cada mês** em
que `monthly/` ainda não tem arquivo daquele mês (não "só no dia 1º"): container parado no dia 1º ainda gera a
cópia do mês, e o primeiro run depois do deploy de 2026-10-26 semeia a pasta. Decisão do usuário 2026-10-16: o `now` do deploy caía em `daily/`, e um dia
com 9 deploys guardava 9 dumps; um deploy novo torna inútil o backup do deploy anterior, então `predeploy/`
fica com 1 só. O `now` não grava heartbeat nem a data do último sucesso: um deploy às 02h não pode pular o
backup das 03h daquele dia.

## Como funciona (`pg_backup.sh`)

| Subcomando | O que faz |
| --- | --- |
| `run` (default) | Loop de 60s. Faz 1 backup por dia local, a partir de `BACKUP_HOUR_LOCAL` (3 = 03:00 `America/Sao_Paulo`). A checagem é `>=`, então um restart depois das 03h ainda recupera o dia perdido. Falha → nova tentativa em 15 min. |
| `now` | Faz 1 backup imediato em `predeploy/` e sai com 0/1. É o modo manual e o do "backup antes do deploy". Não toca `daily/`/`weekly/`. |
| `healthcheck` | Fica unhealthy se o último **sucesso** tiver mais de 26h. Há tolerância de 26h desde o start do container, para o deploy recém-feito não aparecer unhealthy. |
| `select-expired N` | Recebe nomes no stdin e devolve o que a retenção apaga (tudo menos o mais novo de cada um dos N dias mais recentes). Testado em `backend/tests/scripts/test_pg_backup_retention.py`. |
| `monthly-due YYYY-MM` | Recebe a listagem de `monthly/` no stdin; sai 0 se aquele mês ainda não tem cópia. Mesmo teste. |

Passos de cada backup (1 linha JSON de log por passo):
1. `pg_dump -Fc --compress=zstd` pelo **socket direto** (`pgsocket`, nunca pgbouncer em transaction mode),
   para um arquivo temporário no volume `pgbackup-tmp`.
2. `pg_restore --list`: valida que o arquivo é um dump íntegro.
3. Cancela upload grande inacabado sob `backups/` (sobra de execução que caiu; parte guardada é cobrada).
4. `b2 file upload` em `daily/`. O CLI faz o large file/multipart sozinho acima do limite e confere o SHA1.
   Depois, `b2 file info` confirma o tamanho exato.
5. Domingo: a mesma coisa em `weekly/`, seguida da retenção semanal. Mês sem cópia em `monthly/`: idem em
   `monthly/`, seguida da retenção mensal.
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
# 1. Escolher o arquivo (daily/, weekly/, monthly/ ou predeploy/)
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
