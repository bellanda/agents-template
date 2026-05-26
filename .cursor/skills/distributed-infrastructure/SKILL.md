---
name: distributed-infrastructure
description: Mapa do ecossistema de ferramentas de alta carga para backend — messaging brokers (NATS, Kafka, RabbitMQ), cache/KV stores (Valkey para cache puro, NATS KV, Memcached, etcd), task queues (Celery, Dramatiq, Sidekiq), workflow engines (Temporal, Restate). Use ao decidir entre essas ferramentas, ao desenhar arquitetura event-driven, ao avaliar quando NATS sozinho basta e quando trocar/somar com outra peça. Foco arquitetural em NATS; cache puro de alta performance é Valkey (fork OSS do Redis). Complementar ao skill `nats-messaging` (broker) e `valkey-cache` (cache).
---

# Distributed Infrastructure — Messaging, State & Coordination

Mapa do ecossistema de ferramentas que resolvem comunicação assíncrona, estado compartilhado, processamento distribuído e coordenação entre serviços. Foco em decisão arquitetural: **quando cada ferramenta brilha, quando fica para trás, e quando você precisa de uma vs. várias**.

## Como pensar nesse ecossistema

São 5 categorias funcionais. Cada uma responde a uma pergunta diferente. Saber em qual categoria sua dor mora é metade da decisão.

| Categoria                | Pergunta que resolve                                                            | Ferramentas principais                            |
| ------------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------- |
| **Messaging brokers**    | Como serviço A fala com serviço B sem acoplar IP/porta?                         | NATS, Kafka, RabbitMQ, Pulsar                     |
| **Cache / state stores** | Onde guardo estado pequeno acessado por todos com latência sub-ms?              | Valkey, Memcached, NATS KV                        |
| **Coordination stores**  | Onde guardo estado **consistente** que define topologia (leader, lock, config)? | etcd, Consul, ZooKeeper, NATS KV                  |
| **Task queues**          | Como rodo trabalho pesado fora do request HTTP com retry/scheduling?            | Celery, Dramatiq, Sidekiq, BullMQ, NATS JetStream |
| **Workflow engines**     | Como orquestro fluxos longos que sobrevivem a crash, deploy e network failure?  | Temporal, Restate, Cadence, Airflow               |

Há sobreposição real. NATS cobre messaging + KV + task queue básico. Valkey cobre cache + KV + queue básico (Streams). Kafka cobre messaging + event sourcing. **A pergunta certa não é "qual ferramenta é melhor", é "quais categorias eu preciso e qual ferramenta cobre múltiplas com qualidade aceitável"**.

> **Nota sobre Valkey vs Redis**: em março de 2024 a Redis Inc. trocou a licença do Redis para SSPL/RSALv2 (não-OSS). A Linux Foundation forkou a base de código (Redis 7.2.4, BSD-3) e criou o **Valkey**, mantido por Google, AWS, Oracle, Ericsson e a comunidade. **API e protocolo são 100% compatíveis** — clientes redis-py/ioredis/jedis funcionam sem mudança. Para cache novo em produção, Valkey é a escolha padrão moderna; "Redis" aparece neste documento apenas em referências históricas a empresas que adotaram antes do fork.

---

## Os 6 padrões fundamentais

Cada padrão é uma forma de comunicar/coordenar. Conhecer os 6 te dá o vocabulário para qualquer arquitetura distribuída.

### 1. Pub/Sub efêmero (broadcast fire-and-forget)

**Intuição**: alguém grita num auditório. Quem está ouvindo escuta. Quem chegou depois perdeu. Quem está distraído também perdeu.

**Por que existe**: desacoplar produtor de consumidores sem precisar saber quem são, quantos são, ou se estão online.

**Quando usar**:

- Invalidação de cache distribuído entre N instâncias
- Telemetria/métricas em tempo real (não crítica)
- Notificações que outro evento vai compensar (heartbeat, presence)
- Eventos onde "perdi um" não derruba ninguém

**Exemplo de fluxo prático — invalidação de cache**:

```
Usuário atualiza email no perfil
    ↓
API instância 3 escreve no Postgres
    ↓
API 3 publica evento: "cache.invalidate.user.42"
    ↓
NATS distribui para TODAS as instâncias (1, 2, 3, 4, ...)
    ↓
Cada instância remove user_id 42 do seu cache local in-memory
    ↓
Próxima leitura busca dados frescos do banco
```

**Por que computacionalmente faz sentido**: você troca uma rede de N×N conexões HTTP entre serviços por um broker central. O custo é O(N) em vez de O(N²).

**Quem usa em escala**: Discord usa NATS pub/sub para presence updates entre seus nós (milhões de events/s). Slack historicamente usou Redis pub/sub para sincronizar estado de canais entre instâncias. Twitter usou Memcached + custom pub/sub no início.

**Ferramentas que servem**: NATS Core (ideal), Valkey pub/sub (segunda opção, mas fire-and-forget sem queue groups), Kafka (overkill mas funciona).

---

### 2. Request-Reply (RPC sobre messaging)

**Intuição**: telefonema entre serviços. Eu ligo, você atende, conversamos, eu desligo. Nenhum dos dois precisa saber o telefone do outro — a operadora roteia.

**Por que existe**: chamadas síncronas internas de baixa latência sem precisar montar HTTP framework, descobrir endpoint, configurar load balancer e fazer health check.

**Quando usar**:

- Validação de token entre API gateway e auth service
- Pricing engine, geocoding, currency conversion entre serviços
- Qualquer chamada interna onde HTTP teria overhead alto

**Exemplo de fluxo prático — validação de token**:

```
Cliente envia request com JWT
    ↓
API Gateway recebe, precisa validar
    ↓
Gateway faz request: nc.request("auth.validate", token, timeout=200ms)
    ↓
NATS roteia para qualquer instância de auth-service livre (queue group)
    ↓
auth-service decodifica JWT, verifica em KV/DB, responde
    ↓
Gateway recebe resposta em ~1-2ms (HTTP seria 5-20ms)
    ↓
Gateway prossegue com o request original
```

**Por que computacionalmente faz sentido**:

| Métrica             | HTTP interno            | NATS Request-Reply                  |
| ------------------- | ----------------------- | ----------------------------------- |
| Latência típica     | 5–20ms                  | 0.5–2ms                             |
| Service discovery   | DNS / mesh / Consul     | Subject (built-in)                  |
| Load balancing      | Externo (NLB, Envoy)    | Queue group (built-in)              |
| Connection overhead | TCP handshake por req   | Connection persistente multiplexada |
| Timeout/retry       | Cada cliente implementa | Built-in no protocolo               |

**Quem usa em escala**: HashiCorp Consul Connect usa pattern parecido para mesh interno. Synadia (criadora do NATS) tem cases de empresas trocando gRPC interno por NATS Request-Reply para microserviços de baixa latência. GE Aviation usa NATS para comunicação entre componentes de aeronaves.

**Ferramentas que servem**: NATS (ideal), gRPC (mais cerimonial mas funciona), HTTP (se latência não importa).

---

### 3. Queue Groups (competing consumers)

**Intuição**: fila do banco com 5 caixas. Próximo cliente vai ao primeiro caixa livre. Se um caixa sai pro almoço, os outros 4 absorvem o fluxo. Se chega cliente demais, fila cresce até alguém atender.

**Por que existe**: distribuir trabalho horizontalmente sem orquestrador central. Cada worker pega o próximo item livre. Crash de um worker não para a fila.

**Quando usar**:

- Processamento que **não pode rodar inline no request HTTP** porque travaria a API
- Trabalho paralelizável (cada item independente)
- Workloads que precisam absorver picos sem derrubar a API

**Exemplo de fluxo prático — processamento pesado de upload**:

```
Usuário faz upload de vídeo de 500MB
    ↓
API recebe arquivo, salva em S3, retorna 202 Accepted (~200ms)
    ↓
API publica em "tasks.video.transcode" com path do S3
    ↓
NATS entrega para UM worker do pool (10 workers no queue group "video-workers")
    ↓
Worker baixa, transcoda em 4 resoluções (~5min de CPU)
    ↓
Worker publica eventos de progresso, atualiza DB no fim
    ↓
API ficou livre 200ms depois do upload — não bloqueou outros usuários
```

**Padrão crítico**: a fila desacopla **produtor rápido** (HTTP request, ~ms) de **consumidor lento** (CPU/IO heavy, ~s/min). Sem essa camada:

- API trava processando
- Worker timeout no request
- Pico de uploads derruba a API inteira
- Não há retry — falhou, perdeu

**Por que computacionalmente faz sentido**: separa o ciclo de vida do request HTTP do ciclo de vida do trabalho real. Você dimensiona API e workers de forma independente. API tem 4 instâncias para responder rápido. Workers tem 20 instâncias para processar batch. Cada um escala pela sua métrica.

**Quem usa em escala**: Cloudflare usa Queue Groups internamente para jobs de configuração. Mailgun para envio de email. Shopify (com Sidekiq) processa bilhões de jobs/dia em queue groups.

**Ferramentas que servem**: NATS Queue Groups (simples, at-most-once), NATS JetStream consumer (durável, at-least-once), RabbitMQ (mais features), Celery/Sidekiq (com Valkey/RabbitMQ atrás).

---

### 4. Persistent Streams (durable log)

**Intuição**: diário do que aconteceu, em ordem. Você pode ler agora. Pode ler amanhã. Pode voltar 3 dias atrás. Pode ter 5 leitores cada um lendo no seu ritmo. O diário guarda tudo até você decidir apagar.

**Por que existe**: garantir que eventos não se percam, permitir replay para debug/reprocessamento, suportar event sourcing como source of truth.

**Quando usar**:

- Order processing, pagamentos — perder evento = perder dinheiro
- Audit trail regulatório
- Event sourcing (estado derivado de log de eventos)
- CDC (capturar mudanças de DB e propagar para outros sistemas)
- Pipelines de dados onde reprocessar é normal

**Exemplo de fluxo prático — pedido em e-commerce**:

```
Cliente clica "comprar"
    ↓
API valida, escreve pedido no Postgres (transaction)
    ↓
API publica em JetStream stream "ORDERS": orders.created.{id}
    ↓
JetStream persiste em disco, replica em 3 nós, retorna ACK
    ↓
Múltiplos consumers leem o stream:
    - inventory-service: decrementa estoque
    - payment-service: cobra cartão
    - email-service: manda confirmação
    - analytics-service: atualiza métricas
    - audit-service: arquiva para compliance
    ↓
Cada consumer ACKs individualmente. Se um crashar, JetStream redelivery.
    ↓
Mês depois, time de fraud analysis pode REPLAYAR todos pedidos do mês
para rodar novo modelo. Stream ainda tem tudo.
```

**Diferença crítica vs Queue Group**:

- Queue Group: 1 mensagem → 1 worker processa → mensagem some
- Stream: 1 mensagem → N consumers diferentes leem → mensagem fica persistida

**Por que computacionalmente faz sentido**: durabilidade + replay são propriedades **emergentes** difíceis de adicionar depois. Se você começou com pub/sub efêmero e descobre que precisa replay, você precisa migrar tudo. Stream desde o início te dá a opção.

**Quem usa em escala**:

- LinkedIn criou o Kafka para isso (eventos de feed, atividade)
- Netflix usa Kafka para tudo de eventos (viewing, clicks, A/B tests)
- Uber migrou todo state change interno para Kafka
- Robinhood, Coinbase usam para order books e trade history
- Em fintech brasileira: Nubank usa Kafka pesado para event sourcing

**Ferramentas que servem**: Kafka (rei absoluto em volume massivo), NATS JetStream (suficiente até ~500k msg/s), Pulsar (concorrente do Kafka), Redpanda (Kafka API mas mais rápido).

---

### 5. KV Store distribuído (shared state)

**Intuição**: quadro branco compartilhado. Qualquer serviço escreve ali, qualquer outro lê. Mudou? Quem está olhando vê na hora. Mas é estado pequeno — config, flags, locks. Não é banco de dados.

**Por que existe**: quando você tem N instâncias, cada uma com seu cache local, alguma coisa precisa ser **a verdade compartilhada** acessível com latência baixa.

**Quando usar**:

- Feature flags com rollout gradual
- Config que muda em runtime sem redeploy
- Locks distribuídos (só um worker roda o cron)
- Idempotência keys (não processar webhook duplicado)
- Service discovery (quem está vivo?)
- Sessões leves (com TTL)
- Leader election (quem é o coordenador agora?)

**Exemplo de fluxo prático — idempotência de webhook de pagamento**:

```
Stripe envia webhook duas vezes (rede instável, retry)
    ↓
Webhook 1 chega na instância A:
    A tenta: kv.create("webhook:evt_abc123", {processed_at: now})
    Sucesso (chave nova).
    A processa pagamento, libera pedido.
    ↓
Webhook 2 (duplicado) chega na instância B:
    B tenta: kv.create("webhook:evt_abc123", {...})
    Falha — KeyExistsError (já existe).
    B ignora, retorna 200 para Stripe.
    ↓
Pedido foi liberado UMA vez, mesmo recebendo o webhook DUAS vezes.
```

**Por que isso é difícil sem KV distribuído**: você teria que coordenar via DB (lento), ou manter cache local (cada instância tem cópia diferente, bug clássico), ou serializar tudo numa instância (perde escalabilidade).

**Por que computacionalmente faz sentido**: KV distribuído te dá compare-and-swap atômico, watch reativo, e TTL automático — primitivas difíceis de implementar à mão.

**Subdivisão importante**: existem **dois tipos de KV** que parecem iguais mas são fundamentalmente diferentes:

| Tipo                                          | Foco                            | Consistência                 | Uso                                          |
| --------------------------------------------- | ------------------------------- | ---------------------------- | -------------------------------------------- |
| **Cache KV** (Valkey, Memcached, NATS KV)     | Latência sub-ms                 | Eventual ou config-dependent | Cache HTTP, sessões, contadores              |
| **Coordination KV** (etcd, Consul, ZooKeeper) | Consistência forte (Raft/Paxos) | Linearizável                 | Leader election, K8s state, service registry |

**Não confunda os dois.** Você não roda Kubernetes em Valkey (consistência fraca). Não roda cache HTTP em etcd (latência alta).

NATS KV ocupa um meio-termo: é construído sobre JetStream (Raft), então tem consistência boa, mas latência maior que Valkey (~1-3ms vs ~0.1ms).

**Quem usa em escala**:

- Kubernetes inteiro roda em etcd (toda decisão de orquestração)
- HashiCorp ecosystem usa Consul (Vault, Nomad)
- Twitter usou ZooKeeper para coordenação interna
- Praticamente toda startup moderna usa Redis/Valkey para cache/session (pré-2024 = Redis; pós-fork = Valkey é o default OSS)
- Discord usa Redis para presence + NATS KV para config interno

**Ferramentas que servem**:

- Cache puro: **Valkey** (default moderno), Memcached (sem features extras)
- KV transacional: NATS KV, Valkey (com Lua scripts ou MULTI/EXEC)
- Coordination forte: etcd, Consul, ZooKeeper

---

### 6. Object Store (blobs entre serviços)

**Intuição**: Dropbox temporário entre serviços. Serviço A sobe um arquivo, serviço B baixa. Sem precisar montar disco compartilhado, sem precisar de S3 dedicado, sem passar bytes pelo broker de mensagens.

**Por que existe**: messaging brokers não foram feitos para mover blobs grandes. NATS, Kafka, Rabbit têm limite prático de mensagem (~MB). Object Store (NATS Object Store, Valkey com cuidado, MinIO local) preenche o gap.

**Quando usar**:

- Pipeline multi-etapa que troca arquivos intermediários (vídeo: upload → transcode → encode → CDN)
- Cache de artefatos de build entre CI workers
- Snapshots temporários para debug entre serviços

**Exemplo de fluxo prático — pipeline de processamento de vídeo**:

```
Worker 1 (uploader): salva vídeo bruto no Object Store, publica evento
Worker 2 (transcoder): baixa do Object Store, transcoda, salva resultado, publica
Worker 3 (encoder): baixa, encoda múltiplos bitrates, salva, publica
Worker 4 (cdn-uploader): baixa, manda para S3 final, marca completo
```

**Por que não usar S3 direto**: latência (cada I/O sai pra fora da rede interna), custo (S3 cobra por request), complexidade (credenciais, IAM). Object Store local resolve para artefatos efêmeros.

**Quem usa em escala**: nicho. NATS Object Store é mais novo (2022+). Synadia usa internamente. MinIO domina o caso "S3 local". Para a maioria dos casos, S3 ou disco compartilhado resolvem.

**Ferramentas que servem**: NATS Object Store (se você já tem NATS), MinIO (S3 compatível self-hosted), Valkey com binário pequeno (gambiarra mas existe), S3/R2/GCS (managed).

---

## As ferramentas e seus territórios

### NATS

**Resumo intuitivo**: o "tudo em um" enxuto. Pub/sub, request-reply, queue groups, streams, KV, object store — tudo num binário Go de ~15MB. Filosofia: primitivas limpas, você compõe a lógica.

**Onde brilha**:

- Latência baixa (escrito em Go, otimizado)
- Operacionalmente trivial (binário único, sem ZooKeeper)
- Multi-tenancy real (accounts isoladas)
- Edge / IoT (leaf nodes, MQTT compatibility)
- Stack poliglota (Python + Rust + Go = clientes excelentes)

**Onde fica para trás**:

- Ecossistema de connectors maduros (Kafka tem 100+, NATS tem ~10)
- Stream processing nativo (Kafka Streams, Flink — NATS não tem)
- Retenção massiva multi-TB (Kafka é mais barato pra isso)
- Cache puro de altíssimo throughput (Valkey vence em ~2x latência)

**Empresas**: Synadia (criadora), Mastercard, GE, Walmart, Cloudflare (em partes), Tinder.

---

### Valkey (fork OSS do Redis)

**Resumo intuitivo**: RAM compartilhada com superpoderes. Latência sub-ms. Estruturas de dados ricas (strings, hashes, lists, sets, sorted sets, streams, bitmaps, HyperLogLog, geospatial). Fork BSD-3 mantido pela Linux Foundation (Google, AWS, Oracle, Ericsson) a partir do Redis 7.2.4 — protocolo RESP idêntico, clientes Redis funcionam sem mudança.

**Por que Valkey e não Redis**:

- Em março/2024 a Redis Inc. trocou licença para SSPL/RSALv2 (não-OSS). AWS, Google e a comunidade forkaram a base.
- Valkey 8.x já passou Redis em throughput em vários benchmarks (multi-threading I/O melhorado, Linux io_uring).
- BSD-3: nenhuma cláusula anti-comercial. Você pode rodar como serviço, redistribuir, modificar.
- Roadmap aberto na Linux Foundation; Redis Inc. virou produto comercial.

**Onde brilha**:

- **Cache**: latência ~0.1ms (UDS) / ~0.3ms (TCP local), ninguém chega perto sustentadamente
- **Rate limiting com sliding window**: sorted sets resolvem em 5 linhas
- **Leaderboards / rankings**: ZADD/ZRANGE são imbatíveis
- **Session store**: TTL nativo, latência baixa
- **Filas pequenas (Streams)**: até ~100k msg/s funciona
- **Contadores atômicos**: INCR/INCRBY a milhões de ops/s

**Onde fica para trás**:

- Persistência boa mas não é ACID (RDB/AOF têm trade-offs)
- Cluster mode tem caveats (slot resharding, hash tags para multi-key)
- Não substitui DB nem broker de eventos sério (Streams é limitado vs Kafka/JetStream)

**Empresas que usam (Redis na época, Valkey é a continuação OSS)**: Twitter (timeline cache), Instagram (feed), Stack Overflow (caching de tudo), Snapchat, Pinterest, Uber. AWS ElastiCache e Google Memorystore agora oferecem Valkey como produto gerenciado.

**Por que ninguém substitui Valkey para cache puro**: latência. Valkey em socket Unix faz ~0.05ms. NATS KV faz 1-3ms. Postgres com índice faz 0.5-2ms. Para um cache HTTP que serve 5000 req/s, esses milissegundos viram orçamento de p99.

> Skill complementar: `valkey-cache` cobre patterns operacionais (cache-aside, sliding window, atomic counters, pipelining, invalidação event-driven).

---

### Kafka

**Resumo intuitivo**: log distribuído imensamente escalável. Imagina um arquivo append-only que cresce para sempre, é replicado em N nós, e múltiplos leitores leem em paralelo no seu próprio ritmo.

**Onde brilha**:

- Throughput massivo sustentado (>1M msg/s real)
- Retenção longa (semanas/meses) barata
- **Ecossistema**: Kafka Connect (centenas de connectors), Kafka Streams (DSL), KSQL (SQL sobre stream), Debezium (CDC battle-tested)
- Event sourcing como produto core

**Onde fica para trás**:

- Operacionalmente pesado (ZooKeeper historicamente, agora KRaft, mas ainda complexo)
- Latência maior que NATS (~5-50ms vs 0.5-5ms)
- Overkill abaixo de ~50k msg/s sustained
- Curva de aprendizado íngreme (partitions, consumer groups, offsets, rebalances)

**Empresas**: LinkedIn (criadora), Netflix, Uber, Airbnb, Pinterest, Walmart. **Brasil**: Nubank, iFood, Mercado Livre — todas usam Kafka pesado.

**Quando NATS não substitui Kafka**:

- Você precisa de Debezium para CDC
- Volume sustentado > 500k msg/s
- Ecossistema Kafka é parte do stack do time de dados (Flink, Spark Streaming)
- Retenção > 30 dias multi-TB

---

### RabbitMQ

**Resumo intuitivo**: correios — exchanges são centros de distribuição, queues são caixas postais, bindings são rotas. Foco em routing rico via AMQP.

**Onde brilha**:

- Routing por header (único caso onde NATS não cobre nativo)
- Priority queues nativas
- Dead Letter Exchange declarativo
- Maturidade operacional (existe desde 2007)

**Onde fica para trás**:

- Throughput menor que NATS/Kafka
- Operação mais complexa (Erlang/OTP cluster)
- Persistência cara comparada a Kafka/JetStream
- Cluster mode tem limitações conhecidas

**Empresas**: Reddit (job queue histórica), Instagram (early days), MongoDB Atlas, Mozilla.

**Quando RabbitMQ ainda ganha de NATS**: você precisa de routing por header complexo OU priority queues nativas. Caso contrário, NATS substitui inteiro com menos peso operacional.

---

### Celery / Dramatiq / Sidekiq / BullMQ

**Resumo intuitivo**: framework completo de fila de tarefas com bateria incluída. Não é broker — é a **camada de aplicação** sobre um broker (Valkey/Redis, RabbitMQ).

**Onde brilham**:

- Retries com exponential backoff out of the box
- Scheduling/cron (Celery Beat, Sidekiq Cron)
- Task chains, groups, chords (Celery Canvas)
- Monitoring UI (Flower, Sidekiq Web)
- 10+ anos de bug fixes em casos extremos (poison pills, retry storms, idempotência)

**Onde ficam para trás**:

- Linguagem-específicos (Celery=Python, Sidekiq=Ruby, BullMQ=Node)
- Acoplados ao broker (Celery+Valkey ou Celery+Rabbit)
- Performance inferior a NATS JetStream cru
- Você herda decisões de design (Celery tem dívida técnica conhecida)

**Empresas**: Mozilla (Celery), Instagram early days (Celery), Shopify (Sidekiq, processa bilhões de jobs/dia), GitHub (Sidekiq).

**Quando Celery vale**:

- Stack 100% Python
- Workflows com chains complexos (`task1 | task2 | task3`)
- Time não quer reimplementar primitives de retry/scheduling

**Quando NATS substitui**:

- Stack poliglota (workers em Rust/Go também)
- Workflows simples (publish → process → ack)
- Você prefere código explícito a framework opinativo

---

### Temporal / Restate / Cadence

**Resumo intuitivo**: computador em câmera lenta. Você escreve código que parece síncrono — mas o engine garante que ele sobrevive a crash, deploy, network failure, e roda exatamente uma vez do começo ao fim, mesmo que leve dias.

**Onde brilham**:

- Workflows longos (horas, dias, semanas)
- Sagas distribuídas (compensação automática em falha)
- State machines duráveis com lógica complexa
- Garantias de exactly-once em fluxos de negócio

**Onde ficam para trás**:

- Operação complexa (Temporal Cluster + Cassandra/Postgres + ElasticSearch)
- Curva de aprendizado alta (workflow vs activity, determinismo)
- Overkill para tasks simples
- Custo operacional grande

**Empresas**: Coinbase (workflows de transação), Snap (engagement workflows), Stripe (billing internamente em Cadence), Doordash (Cadence/Temporal), Uber (Cadence — criadora).

**Quando Temporal vale**:

- Você está escrevendo state machine pela 3ª vez
- Compliance exige auditabilidade de fluxo
- Workflow tem 10+ etapas com retry/compensation
- Saga distribuída entre serviços

**Quando NATS basta**:

- Workflows curtos (segundos/minutos)
- Sem necessidade de compensation automático
- Time pequeno que não vai operar Cassandra

---

### Memcached

**Resumo intuitivo**: Valkey sem features. Só GET/SET/DELETE com TTL. Mais simples, sem persistência, foco maníaco em throughput de cache.

**Onde brilha**:

- Cache puro distribuído com sharding consistente
- Footprint mínimo
- Throughput levemente superior a Valkey em cenários muito específicos (workload 100% GET/SET, sem estruturas)

**Onde fica para trás**:

- Sem estruturas de dados (sorted sets, lists, hashes)
- Sem persistência opcional
- Sem pub/sub
- Valkey cobre tudo que Memcached faz e mais

**Empresas**: Facebook (criadora, ainda usa em escala massiva), historicamente muitas grandes — mas Redis/Valkey tomou o espaço.

**Veredito**: hoje, escolher Memcached over Valkey exige justificativa específica. Default é Valkey.

---

### etcd / Consul / ZooKeeper

**Resumo intuitivo**: KV store **consistente** (Raft/Paxos) para infraestrutura, não para aplicação. São lentos (latência alta) mas garantem que toda leitura vê o último write.

**Onde brilham**:

- Service discovery
- Leader election
- Distributed locks fortes
- K8s/Nomad state
- Configuração crítica de cluster

**Onde ficam para trás**:

- Latência alta (10-100ms) — não serve para cache de aplicação
- Throughput baixo (centenas a milhares de ops/s)
- Não armazena dados de negócio

**Empresas**: Kubernetes (etcd), HashiCorp stack (Consul), Twitter histórico (ZooKeeper).

**Para sua app**: provavelmente não usa diretamente. Você usa K8s, K8s usa etcd. Você não precisa pensar nisso.

---

## Matriz comparativa massiva

### Por categoria funcional

| Necessidade                       | Melhor                   | Bom                 | Aceitável            | Não use                      |
| --------------------------------- | ------------------------ | ------------------- | -------------------- | ---------------------------- |
| Cache HTTP sub-ms                 | **Valkey**               | Memcached           | NATS KV              | Postgres                     |
| Pub/sub efêmero                   | NATS Core                | Valkey pub/sub      | Kafka                | RabbitMQ                     |
| RPC interno baixa latência        | NATS Request-Reply       | gRPC                | HTTP/2               | REST/HTTP1                   |
| Task queue simples                | NATS Queue Group         | Valkey Streams      | RabbitMQ             | Kafka                        |
| Task queue com retries/scheduling | NATS JetStream + código  | Celery/Dramatiq     | Sidekiq              | DIY com Postgres             |
| Event log persistente médio       | NATS JetStream           | RabbitMQ Streams    | Kafka                | Valkey Streams               |
| Event log persistente massivo     | Kafka                    | Redpanda            | Pulsar               | NATS (acima de 500k/s)       |
| Rate limiting sliding window      | **Valkey** (sorted sets) | NATS KV (manual)    | Postgres (lento)     | —                            |
| Feature flags / config dinâmico   | NATS KV                  | Valkey              | etcd/Consul          | DB direto                    |
| Idempotência keys                 | NATS KV                  | Valkey (SETNX)      | Postgres unique      | —                            |
| Distributed lock (curto)          | Valkey (Redlock)         | NATS KV             | etcd                 | —                            |
| Distributed lock (forte)          | etcd                     | Consul              | ZooKeeper            | Valkey (Redlock controverso) |
| Service discovery                 | Consul                   | etcd                | NATS subjects        | DNS/manual                   |
| CDC para warehouse                | Kafka + Debezium         | Pulsar + connectors | NATS + custom        | DIY                          |
| Workflow longo durável            | Temporal                 | Restate             | NATS + lógica custom | Celery chains                |
| Stream processing real-time       | Flink                    | Kafka Streams       | Materialize          | DIY                          |
| Object/blob temporário            | NATS Object Store        | MinIO               | Valkey (pequeno)     | —                            |

### Por característica técnica

| Característica        | NATS               | Valkey             | Kafka          | RabbitMQ       | Celery           |
| --------------------- | ------------------ | ------------------ | -------------- | -------------- | ---------------- |
| Latência mínima       | ~0.5ms             | ~0.1ms             | ~5ms           | ~2ms           | depende broker   |
| Throughput máximo     | ~10M msg/s (core)  | ~1M ops/s (8.x)    | >1M msg/s      | ~100k msg/s    | depende broker   |
| Persistência          | JetStream (sim)    | RDB/AOF            | sim (default)  | configurável   | via broker       |
| Replay                | JetStream sim      | Streams limitado   | sim            | não nativo     | não              |
| Routing rico          | wildcards + queue  | pub/sub básico     | partition key  | exchanges AMQP | via broker       |
| Footprint operacional | 1 binário Go ~15MB | 1 binário C ~5MB   | JVM + ZK/KRaft | Erlang cluster | broker + workers |
| Multi-tenancy         | accounts nativo    | databases (fraco)  | ACLs           | vhosts         | não              |
| Idiomas (clients)     | 40+                | 50+ (Redis-compat) | 30+            | 30+            | Python only      |
| Curva de aprendizado  | baixa              | baixa              | alta           | média          | média            |
| Custo operacional     | baixo              | baixo              | alto           | médio          | médio            |
| Licença               | Apache 2.0         | BSD-3 (OSS)        | Apache 2.0     | MPL 2.0        | BSD              |

### Quando NATS sozinho **basta** (e você não precisa de mais nada)

| Você está construindo                   | NATS basta?                      |
| --------------------------------------- | -------------------------------- |
| MVP de startup, qualquer domínio        | ✅ Sozinho, sem Valkey nem Kafka |
| API com até ~5000 req/s                 | ✅ NATS Core + JetStream         |
| Sistema com até ~100k events/s          | ✅ JetStream aguenta             |
| Microserviços poliglotas (Py/Rust/Go)   | ✅ Cliente excelente em todas    |
| Pub/sub para realtime (chat, presence)  | ✅ Core é ideal                  |
| Task queue com retries simples          | ✅ JetStream                     |
| Feature flags + config                  | ✅ KV                            |
| Idempotência de webhooks                | ✅ KV                            |
| Outbound webhooks com retry exponencial | ✅ JetStream                     |
| Workflow simples (3-5 etapas)           | ✅ JetStream + código            |

### Quando NATS **não basta** e você adiciona uma peça

| Sintoma concreto                                 | Adicione                | Por quê                                        |
| ------------------------------------------------ | ----------------------- | ---------------------------------------------- |
| p99 do cache HTTP > 5ms impacta UX               | **Valkey**              | Latência sub-ms, NATS KV não chega             |
| Rate limiting precisa sliding window por usuário | **Valkey**              | Sorted sets resolvem; NATS não tem estrutura   |
| Leaderboard real-time de milhões de usuários     | **Valkey**              | ZADD/ZRANGE imbatíveis                         |
| Volume sustained > 500k msg/s 24h                | Kafka                   | JetStream não foi feito para isso              |
| Precisa CDC de Postgres para warehouse           | Kafka + Debezium        | Ecossistema maduro, NATS faria à mão           |
| Workflows com 10+ etapas, sagas, compensação     | Temporal                | Reescrever em código fica frágil               |
| Compliance exige audit trail imutável anos       | Kafka (retenção barata) | JetStream tem custo maior em volume            |
| Routing por header AMQP complexo                 | RabbitMQ                | NATS não tem nativo                            |
| Time tem 50 engenheiros e está em Series C+      | Provavelmente Kafka     | Ecossistema, contratação, ferramentas de dados |

### Onde cada um **fica para trás**

| Ferramenta    | Fica para trás quando              | Por quê                                     |
| ------------- | ---------------------------------- | ------------------------------------------- |
| **NATS**      | Volume sustentado > 500k msg/s     | Não foi otimizado para esse regime          |
| **NATS**      | Cache puro de altíssimo throughput | Latência ~10x maior que Valkey              |
| **NATS**      | Stream processing nativo           | Não tem DSL como Kafka Streams              |
| **NATS**      | CDC com schema registry            | Ecossistema Kafka domina                    |
| **Valkey**    | Mensageria séria multi-consumer    | Pub/sub é fire-and-forget; Streams limitado |
| **Valkey**    | Persistência crítica               | RDB/AOF têm trade-offs, não é DB            |
| **Valkey**    | Volume massivo de eventos          | Não foi feito para isso                     |
| **Kafka**     | Latência abaixo de 5ms             | Arquitetura penaliza latência baixa         |
| **Kafka**     | Footprint pequeno                  | JVM + ZK/KRaft é pesado                     |
| **Kafka**     | Stack pequena (até Series A)       | Operação cara, complexidade alta            |
| **RabbitMQ**  | Throughput máximo                  | NATS/Kafka vencem                           |
| **RabbitMQ**  | Replay de eventos                  | Não foi desenhado para isso                 |
| **Celery**    | Stack poliglota                    | Python only                                 |
| **Celery**    | Cargas extremas                    | Overhead do framework                       |
| **Memcached** | Qualquer caso fora cache puro      | Sem features que Valkey tem                 |
| **Temporal**  | Workflows curtos (segundos)        | Overhead operacional não compensa           |

---

## Stack recomendada por estágio

### Pré-MVP / Solo / 1–3 devs

```
FastAPI + Granian + asyncpg + Postgres
NATS (single node) — pub/sub + JetStream + KV
```

**Não adicione**: Valkey, Kafka, RabbitMQ, Celery, Temporal.
**Por quê**: cada componente é dívida operacional. Comece minimal.

### MVP em produção / Seed / 3–10 devs / até 100k MAU

```
FastAPI + Granian + asyncpg + Postgres (read replica opcional)
NATS cluster 3 nós — pub/sub + JetStream + KV
Valkey (opcional, UDS local) — só se cache HTTP for crítico
```

**Não adicione**: Kafka, Celery, Temporal.
**Por quê**: stack ainda gerenciável por 1 SRE part-time.

### Series A / 10–30 devs / 100k–1M MAU

```
FastAPI + Granian + asyncpg + Postgres (cluster com replicas)
NATS cluster 5 nós — JetStream com replicação 3
Valkey cluster — cache + rate limit + leaderboards
+ Considerar: Temporal para workflows críticos (billing, onboarding longo)
```

**Adicione com sinal claro**: Kafka se time de dados pediu (analytics pipeline).

### Series B+ / 30+ devs / 1M+ MAU

```
Stack acima +
Kafka para event log central + CDC (Debezium para warehouse)
Temporal para workflows duráveis
ElasticSearch/OpenSearch para search
ClickHouse/Materialize para analytics em real-time
```

**Filosofia**: cada peça nova precisa de sponsor (alguém responsável por operar).

---

## Decisões fáceis de errar

### "Valkey substitui broker"

**Não.** Valkey pub/sub é fire-and-forget igual NATS Core, mas sem queue groups, sem JetStream, sem multi-tenancy. Valkey Streams é limitado comparado a JetStream/Kafka. Use Valkey para cache + KV; broker separado (NATS).

### "Kafka é sempre melhor que NATS porque é mais conhecido"

**Não.** Kafka é melhor em escala massiva e ecossistema. Em latência, footprint e simplicidade operacional, NATS vence. Para a maioria das startups (até 500k msg/s), NATS é a escolha técnica e operacional correta.

### "NATS KV substitui Valkey"

**Parcial.** Para feature flags, config, idempotência, locks: substitui. Para cache HTTP de alto throughput, rate limiting sliding window, leaderboards: não substitui (Valkey vence em latência ~10x). Use ambos quando latência importa.

### "Posso usar Redis em vez de Valkey, dá no mesmo?"

**Tecnicamente sim, estrategicamente não.** API e protocolo são idênticos hoje (Valkey forkou Redis 7.2.4). Mas Redis pós-2024 é SSPL/RSALv2 — você não pode rodar como serviço (cloud) sem licença comercial, e o ecossistema OSS migrou (AWS ElastiCache default = Valkey, Google Memorystore = Valkey, distribuições Linux empacotam Valkey). Para projetos novos, Valkey é a escolha defensiva: BSD-3, governança neutra, e Valkey 8.x já tem features (multi-threading I/O agressivo) que Redis OSS 7.2 não tem.

### "Vou usar Kafka desde o MVP para 'não migrar depois'"

**Erro caro.** Kafka custa ~5x mais em ops do que NATS. "Não migrar depois" é antecipar custo de uma escala que provavelmente nunca chega. Comece simples. Migre quando dor for real.

### "Celery é o jeito Python de fazer task queue"

**Era.** Hoje, NATS JetStream + worker pool em ~50 linhas substitui 80% dos casos com mais clareza e melhor performance. Celery vale quando você usa Canvas pesadamente ou quando 100% da equipe é Python iniciante.

### "Temporal é overkill"

**Depende.** Para workflows curtos: sim. Para billing com retry de cartão por 7 dias, ou onboarding multi-etapa que sobrevive a deploy, ou saga distribuída entre 4 serviços: Temporal paga em qualidade de sono.

### "Postgres pode fazer tudo isso"

**Parcial.** Postgres com `LISTEN/NOTIFY` faz pub/sub básico. `SELECT FOR UPDATE SKIP LOCKED` faz fila simples. JSONB faz cache. **Mas**: latência maior, escala vertical, contention em workloads de alta concorrência. Vale como início; não vale quando volume sobe.

---

## Filosofia operacional (single-machine high-performance)

Você está numa filosofia específica e válida: **espremer hardware moderno antes de distribuir**. Uma máquina com 32 cores + 128GB RAM + NVMe + Postgres bem configurado + cache local + NATS embedded resolve volumes que em 2010 exigiriam cluster.

**Princípios que reforçam essa abordagem**:

1. **Latência local sempre vence latência de rede**: Postgres em socket Unix > Postgres em TCP local > Postgres em rede. Cada hop custa 0.1-1ms.
2. **Cache por worker (in-process) + cache distribuído (Valkey/NATS KV)**: dois níveis. L1 in-memory por worker (free, sub-microssegundo), L2 distribuído (sub-ms, compartilhado). Valkey via UDS no mesmo host = ~0.05ms.
3. **NATS embedded ou local**: NATS server no mesmo host da API tem latência < 0.1ms. Vale enquanto você está single-machine.
4. **Postgres vertical ANTES de horizontal**: 1 Postgres de 32 cores aguenta MUITO. Read replica antes de sharding. Sharding antes de microserviço.
5. **Async até o fim**: nada de `requests`, `psycopg2` síncrono. asyncpg, anyio, run_in_threadpool para CPU-bound apenas.

**Quando essa filosofia falha**:

- Quando você precisa de HA real (single machine = SPOF)
- Quando o volume passa do que uma máquina aguenta
- Quando você precisa de geo-distribution

Até lá: você está fazendo certo. Continue medindo, continue espremendo.

---

## Resumo de uma frase

> NATS cobre messaging + KV + queue básico com excelência operacional; Valkey (fork OSS BSD-3 do Redis) cobre cache + estruturas de dados ricas com latência sub-ms imbatível; Kafka cobre event sourcing massivo com ecossistema maduro; o resto são especializações que você adiciona quando o sinal aparece, não antes.
