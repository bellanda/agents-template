---
name: infra
description: PORTÃO obrigatório de infraestrutura distribuída de backend — messaging, cache e coordenação de alta carga. INVOCAR ANTES de QUALQUER trabalho de infra — (1) DECIDIR ferramenta/arquitetura event-driven (NATS vs Kafka vs RabbitMQ; Valkey vs Memcached vs NATS KV; Celery/Dramatiq vs JetStream; Temporal/Restate; etcd/Consul; quando NATS sozinho basta vs quando somar peça); (2) IMPLEMENTAR pattern NATS com nats-py (Pub/Sub, Request-Reply, Queue Groups, JetStream stream/consumer/ack, KV Store, wildcards, reconnect, drain); (3) IMPLEMENTAR cache/throttle com valkey-py (cache-aside, sliding window rate limit, contador atômico INCR, pipeline batching, invalidação event-driven, versioned keys, SCAN, Lua CAS, TTL por categoria). Checklist + roteia pras references profundas. REGRA DE FRONTEIRA inegociável: messaging → NATS, cache → Valkey, NUNCA confunda. NUNCA Valkey para eventos cross-service (é trabalho do NATS); NUNCA `KEYS *` em prod (use SCAN); NUNCA `decode_responses=True` global (bytes + orjson no boundary); NUNCA `json` em vez de `orjson`; NUNCA cache sem TTL; NUNCA Kafka/Celery/Temporal "pra não migrar depois" antes do sinal real.
---

# Infra — O Portão (messaging · cache · coordenação)

Ponto de entrada único de infraestrutura distribuída. **NUNCA escreva código de messaging/cache nem
escolha uma ferramenta de alta carga sem passar por aqui.** A natureza da tarefa decide a reference;
o checklist roteia.

## Regra de fronteira (memorize antes de tudo)

> **messaging → NATS · cache → Valkey.** Nunca confunda os dois. Valkey Pub/Sub só como fan-out de
> invalidação in-process onde NATS não está disponível; evento cross-service é **sempre** NATS.
> Stream durável é **sempre** NATS JetStream (não Valkey Streams).

## Checklist (em ordem; desça o que a tarefa exige)

- [ ] **1. Decisão arquitetural** — escolher/avaliar ferramenta (NATS/Kafka/RabbitMQ/Valkey/Memcached/
  Celery/Temporal/etcd), desenhar arquitetura event-driven, decidir se NATS sozinho basta ou somar peça
  → **`references/decision-map.md`** (mapa de 5 categorias, 6 padrões, matriz comparativa, stack por estágio).
- [ ] **2. NATS (broker)** — implementar com nats-py: Pub/Sub, Request-Reply, Queue Groups, JetStream
  (stream/consumer/ack), KV Store, wildcards, reconnect/drain → **`references/nats-messaging.md`**.
- [ ] **3. Valkey (cache)** — implementar com valkey-py: cache-aside, sliding window, contadores atômicos,
  pipeline, invalidação event-driven, versioned keys, SCAN, Lua, TTL → **`references/valkey-cache.md`**
  (código completo em `references/valkey/*.py`).
- [ ] **4. Agendar por horário ("faça X em T, uma vez": SLA, lembrete, expiração, cadência)** — `DueQueue`
  (ZSET Valkey + claim Lua com lease + wake JetStream + reconcile; efeitos after-commit; avisa-uma-vez
  no Postgres) → **`references/due-queue.md`**.

## Invariantes não negociáveis (sempre)

- Fronteira messaging/cache (acima). Stream durável → JetStream; cache sub-ms → Valkey UDS.
- Valkey: conexão **UDS-only** (`unix:///run/valkey/valkey.sock`); `decode_responses=False` + `orjson`
  no boundary; **sempre** TTL (`ex=`); **NUNCA** `KEYS *` (use `scan_iter`); namespace por prefixo de propósito.
- NATS: `timeout` obrigatório em Request-Reply; `durable=` em consumer que sobrevive a restart; `msg.ack()`
  explícito em JetStream; reconnect/drain em produção.
- Runtime em prod (guardas por app, `tests/scripts/test_runtime_infra_config.py`; `scripts/fleet_drift.py
  --apps <repos> [--json] [--strict]` do template compara os arquivos do manifest): orçamento de memória e
  workers no teto (`APP_LIMIT_CAP_MB`, `MAX_GRANIAN_WORKERS` — ajuste só quando o orçamento mudar de
  propósito; kailos hoje 8400 MB); `compose.yaml` base NÃO declara `logging` nos serviços da app (vale o
  `compose.prod.yaml` com journald; rule `logs.md`); serviço que não serve rota (agent-worker, cron-worker)
  tem healthcheck por heartbeat (toca um arquivo, o healthcheck confere a idade; akmeo `compose.yaml`).
  Streams/SSE e `LISTEN` seguem o contrato de `database` → `tenancy-and-writes.md` §3 e `valkey-cache.md` §6.
- Decisão: comece minimal (NATS sozinho cobre messaging+KV+queue até ~500k msg/s). Some Kafka/Celery/
  Temporal **só com sinal concreto** — NUNCA "pra não migrar depois".

## References

- `references/decision-map.md` — mapa do ecossistema (quando cada ferramenta brilha/fica pra trás) — antes era `distributed-infrastructure`.
- `references/nats-messaging.md` — os 5 patterns NATS com nats-py (delivery guarantees, código async).
- `references/postgres-tiers.md` — tiers de memória do `prod.conf` (shared-16gb / dedicated-16gb); não há gerador, o arquivo é por repo.
- `references/due-queue.md` — motor de tempo `DueQueue` (kailos canônico): Valkey acorda / Postgres decide, lease+CAS, reconcile, after-commit, testes.
- `references/valkey-cache.md` — patterns de cache/throttle com valkey-py → código working em `references/valkey/`.
