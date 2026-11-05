# DueQueue — "faça X no instante T, exatamente uma vez"

> Reference do gate `infra`. Abra ANTES de agendar qualquer coisa por horário (SLA, lembrete, expiração,
> cadência, repescagem, "avisa se ninguém respondeu em N min"). Canônico: **kailos**
> (`backend/src/api/services/scheduling/`). Não crie `asyncio.sleep`/cron por entidade nem polling de
> tabela: use uma `DueQueue`. Decisão: CRM 2030, 2026-11-05.

## Modelo mental

> **Valkey acorda, Postgres decide.** O ZSET do Valkey (`member -> próximo despertar em epoch ms`) é só
> uma dica de "olhe esta linha agora". Quem decide o que fazer é o handler, relendo o Postgres. Perder o
> ZSET (flush, restart) nunca perde trabalho: o `reconcile` o reconstrói do banco.

Uma fila = 1 ZSET (`due:{name}:zset`) + 1 subject JetStream que carrega `{member, lease}` + 1 consumer
durável. `member = "{kind}:{id}"` (kind sem `:`; split no PRIMEIRO `:`).

## Peças (kailos, `backend/src/api/services/`)

| Arquivo | Papel |
| ------- | ----- |
| `scheduling/due_queue.py` | `DueQueue` (dataclass frozen): `schedule_at`, `wake_now`, `unschedule`, `add_if_missing` (ZADD NX), `claim_due` (Lua), `finish` (Lua CAS), locks por member e de reconcile, `publish_wake`. |
| `scheduling/ticker.py` | `register_due_queue`/`get_due_queue`, `tick_once`, `reconcile_queue`, `run_queue_ticker`, `run_due_tickers` (lifespan: **uma task por fila**). |
| `scheduling/consumer.py` | `run_due_consumer(queue, stop)`: lock do member -> `handler(member, now)` -> `finish` -> ack. Exceção do handler = ack + reagenda em `failure_backoff_s` (nunca NAK/loop). |
| `messaging/streams.py` | declara o stream (`CRM`, work-queue) e os subjects. |
| `messaging/consumers/__init__.py` | registra `("crm-question", lambda stop: run_due_consumer(CRM_QUESTION, stop))`. |
| `crm/question_queue.py` | exemplo mínimo completo: `evaluate_*` (relê o banco, devolve próximo despertar ou `None`), `handle_*_wake`, `reconcile_*_page`, `CRM_QUESTION = register_due_queue(DueQueue(...))`. |

## Como criar uma fila nova (receita)

1. Subject em `streams.py` (stream existente ou novo, `RetentionPolicy.WORK_QUEUE`).
2. Módulo `*_queue.py` com 3 funções + a constante:
   - `handler(member, now) -> datetime | None`: **relê o Postgres**, age uma vez, devolve o próximo
     despertar real (ou `None` = nada mais a fazer). Puro quanto ao relógio: usa o `now` recebido.
   - `reconcile(after_member, limit) -> Sequence[str]`: página ordenada ASC, estritamente depois de
     `after_member`; semeia (ZADD NX com o score real) o que está pendente no banco. **Obrigatório**.
   - `DueQueue(name, stream, subject, durable, lease_s, lock_ttl_s, reconcile, handler)`.
3. Importe o módulo no registro de consumers e em quem agenda (o import registra a fila no ticker).
4. Quem muda o domínio **agenda** via `DueWake` after-commit (abaixo), nunca direto no Valkey.

## Invariantes (cada uma tem teste)

- `claim_due` é Lua atômico: move os vencidos para um score de **lease** (`now + lease_s`). N tickers
  (8 workers Granian) nunca pegam o mesmo member; consumer morto = lease expira = member volta sozinho.
- `finish` é **CAS** (Lua): só reagenda/remove se o score ainda é o NOSSO lease. Um `schedule_at` novo
  durante a avaliação troca o score e o `finish` velho vira no-op (o despertar novo sobrevive).
- JetStream `Nats-Msg-Id = {member}:{lease}`: dedupe de republish do MESMO claim; re-claim após lease
  vencido tem outro lease e passa.
- `reconcile` pagina (1000), 1 worker por vez (lock Valkey, 5 min), ZADD NX: cobre flush do Valkey,
  hook que falhou, primeiro deploy da fila e prazo alterado. O ZSET tem TTL de 24h renovado por ele.
- **Uma task por fila** no ticker: fila com 10.000 vencidos não atrasa a de 1 vencido.
- Score arredondado para CIMA (`ceil` em ms): nunca dispara antes do prazo.
- **"Avisa uma vez" mora no Postgres** (coluna `notified_at` com UPDATE condicional ANTES de enviar, ou
  `UNIQUE (org, dedupe_key)`), nunca só num lock do Valkey: lock expira, Valkey é descartável.
  Aceita at-most-once de propósito quando a falha de envio tem fallback (ex.: faixa no app).
- **Um relógio por decisão**: `now` injetado (`clock=` na fila, `now=` nas funções); proibido
  `time.time()`, `date.today()`, `CURRENT_DATE` dentro de handler (falha só em faixa de horário: UTC
  vira o dia 21h em SP). Recorte por dia = fuso da loja por UM resolvedor (`api/core/timezone.py`
  `store_tz`); **23:59 conta como o mesmo dia** (fim do dia é `[00:00, 24:00)`, 00:00 já é o seguinte).
- O handler é idempotente e tolera despertar velho (devolve o próximo despertar real).

## Efeitos after-commit (`crm/after_commit.py`)

Por quê: acordar a fila ou publicar SSE **antes do COMMIT** faz o handler ler linha velha (ou uma
escrita que sofreu rollback acordar a fila/o celular). Regra: quem escreve nunca chama Valkey/NATS;
registra uma ação e o chamador a executa depois do commit.

- Ações são dataclasses frozen; `defer_after_commit(action)`; handlers por tipo via
  `register_after_commit_handler` (idempotente). `DueWake(queue_name, member, wake_at)` é a ação
  **genérica** de agendamento (handler em `crm/due_wake.py` chama `get_due_queue(name).schedule_at`):
  fila nova não edita este módulo.
- `collect_crm_after_commit()` (async ctx): coleta e roda só na saída limpa; **coletor aninhado entra
  no externo** (o mais externo descarrega). Sem coletor aberto = descarta com warning (o reconcile
  cobre). `discard_crm_after_commit()` para backfill/import/replay (nunca notifica).
- `api/middlewares/crm_after_commit_middleware.py`: ASGI puro abre o coletor por request HTTP; resposta
  >= 400 ou exceção DESCARTA; SSE (`text/event-stream`) descarrega no início da resposta.
- Aceito: ação deferida dentro de SAVEPOINT que depois sofre rollback ainda roda; como todo handler
  relê o Postgres, o pior caso é um despertar/frame espúrio.
- Handler de fila chamado de fora de request abre o coletor ele mesmo
  (`async with pool.acquire() as conn, collect_crm_after_commit():`).

## Testes que guardam (`backend/tests/scheduling/test_due_queue.py`, Valkey+NATS reais)

- `concurrent_tickers_claim_each_member_exactly_once`: 2+ tickers, cada member 1x.
- `expired_lease_after_a_crash_is_reclaimed_with_a_new_lease`: simula consumer morto.
- `finish_cas_keeps_a_wakeup_added_during_evaluation`: o CAS não apaga o despertar novo.
- `valkey_flush_then_reconcile_restores_the_zset_in_pages`: FLUSH + reconcile paginado.
- `nats_redelivery_of_the_same_claim_is_deduped`: mesmo `Nats-Msg-Id` não duplica.
- `handler_exception_backs_off_instead_of_losing_or_hot_looping_the_member`.
- `tick_to_consumer_to_handler_end_to_end_and_busy_member_is_skipped`.
- `a_huge_queue_does_not_starve_another`: 10.000 vencidos em A, 1 em B dentro de um tick.
- `tests/crm/test_after_commit.py`: roda 1x na saída limpa, rollback/exceção/discard não rodam,
  middleware descarrega em 2xx e descarta em 4xx/exceção, `DueWake` agenda na fila nomeada.
- Relógio: `FakeClock` injetado nos testes só do motor; relógio real onde há consumer/ticker de verdade.

## Armadilhas

- Esquecer o `reconcile` = primeiro deploy/flush perde despertares. Teste: zere o ZSET e rode.
- Handler que decide pelo score do ZSET em vez de reler o banco.
- Agendar dentro da transação (fora do `defer_after_commit`).
- `CURRENT_DATE`/`date.today()` em handler ou em teste de fronteira de dia.
