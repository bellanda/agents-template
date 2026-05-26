---
name: nats-messaging
description: NATS messaging patterns with nats-py — Pub/Sub, Request-Reply, Queue Groups, JetStream streams, KV Store. Use when designing event-driven architecture, broadcasting events, building RPC over messaging, or implementing persistent streams.
---

# NATS — Messaging Patterns with Python (nats-py)

Covers the five primary NATS patterns — Pub/Sub, Request-Reply, Queue Groups, JetStream, KV Store — with async Python code, delivery guarantees, and when to pick each. The nats-server runs as a separate process; the app connects via TCP on port 4222.

## 1. Pub/Sub (Core NATS)

**What it solves:** broadcast events to all interested subscribers in real time, fire-and-forget.

**When to use:** cache invalidation, live telemetry, metrics emission, notifications, anything where losing a message while a subscriber is offline is acceptable.

**Delivery guarantee:** at-most-once. If the subscriber is offline, the message is gone.

**Key concept — wildcards:**

- `events.user.login` — exact match
- `events.user.*` — single token wildcard (matches `events.user.login`, not `events.user.login.failed`)
- `events.>` — multi-token wildcard (matches everything under `events.`)

### Flow

```
Publisher                      NATS Server                    Subscriber
   |                              |                              |
   |-- publish("events.user.login", b"user-42") -->|             |
   |                              |-- deliver to all subs on events.> -->|
   |                              |                              |-- message_handler(msg)
```

### Code

```python
import nats
from nats.aio.msg import Msg

nc = await nats.connect("nats://127.0.0.1:4222")

# Subscribe with wildcard — receives ALL events.* messages
async def handler(msg: Msg) -> None:
    print(f"{msg.subject}: {msg.data.decode()}")

await nc.subscribe("events.>", cb=handler)

# Publish to specific subjects — both match events.>
await nc.publish("events.user.login", b"user-42")
await nc.publish("events.system.heartbeat", b"tick-1")

await nc.close()
```

**Critical details:**

- `nc.subscribe(subject, cb=handler)` — the callback is async, invoked per message.
- `nc.flush()` — forces pending publishes to the server; use after subscribe to guarantee the subscription is active before publishing.
- No persistence. If zero subscribers match, the message is silently discarded.

---

## 2. Request-Reply

**What it solves:** synchronous RPC-like calls between services, with timeout.

**When to use:** service-to-service calls where you need a response (get user profile, validate token, calculate price). Replaces HTTP between internal microservices with sub-millisecond latency.

**Key concept:** the client publishes to a subject with an auto-generated reply inbox. The responder reads `msg.reply` and responds to it. NATS handles the routing.

### Flow

```
Client                         NATS Server                    Service
   |                              |                              |
   |-- request("services.greet", b"Ana", timeout=0.5) -->|      |
   |                              |-- deliver to subscriber -->  |
   |                              |                              |-- msg.respond(b"olá, Ana")
   |<-- reply on _INBOX.xxx ------|<-----------------------------|
```

### Code

```python
import nats
from nats.aio.msg import Msg
from nats.errors import NoRespondersError

# Service side — subscribes and responds
async def greet_handler(msg: Msg) -> None:
    name = msg.data.decode()
    await msg.respond(f"olá, {name}".encode())

server_nc = await nats.connect("nats://127.0.0.1:4222", name="greet-service")
await server_nc.subscribe("services.greet", cb=greet_handler)

# Client side — sends request, awaits reply
client_nc = await nats.connect("nats://127.0.0.1:4222", name="api-gateway")
try:
    reply = await client_nc.request("services.greet", b"Ana", timeout=0.5)
    print(reply.data.decode())  # "olá, Ana"
except NoRespondersError:
    print("no service available")
```

**Critical details:**

- `timeout` is mandatory in production. If no responder exists, `NoRespondersError` is raised immediately (NATS detects "no subscribers" server-side).
- `msg.respond(data)` publishes to the auto-generated `_INBOX.*` reply subject.
- Scale the responder with queue groups for load balancing (see next section).

---

## 3. Queue Groups

**What it solves:** distribute work across multiple instances of the same service — only ONE subscriber in the group receives each message.

**When to use:** task processing, email sending, image resizing — any workload where you want horizontal scaling with competing consumers. This is NATS's built-in load balancer.

**Key concept:** subscribers with the same `queue` name form a group. NATS distributes messages round-robin across the group. No extra configuration, no broker queues to declare.

### Flow

```
Publisher                      NATS Server                    Workers
   |                              |                              |
   |-- publish("tasks.resize") -->|                     Worker 0 |
   |                              |-- deliver to ONE -->Worker 1 |
   |                              |                     Worker 2 |
```

### Code

```python
import nats
from nats.aio.msg import Msg

nc = await nats.connect("nats://127.0.0.1:4222")

# 3 workers sharing the "resize-workers" queue group
async def worker_handler(msg: Msg) -> None:
    print(f"processing: {msg.data.decode()}")

for _ in range(3):
    await nc.subscribe("tasks.resize", queue="resize-workers", cb=worker_handler)

# Publish 10 tasks — each goes to exactly ONE worker
for i in range(10):
    await nc.publish("tasks.resize", f"image-{i}".encode())
```

**Critical details:**

- The `queue` parameter is all it takes. No queue declaration, no broker config.
- Without `queue`, ALL subscribers receive every message (fan-out). With `queue`, exactly ONE receives it.
- Works across processes and machines. 10 pods with the same queue group name = automatic load balancing.
- Combine with Request-Reply: multiple responders on the same subject with a queue group, and `nc.request()` gets answered by whichever is free.

---

## 4. JetStream (Persistent Event Streaming)

**What it solves:** durable message storage with replay, acknowledgment, and at-least-once delivery.

**When to use:** order processing, audit trails, event sourcing, any workflow where losing a message is unacceptable. This is NATS's answer to Kafka topics.

**Key concepts:**

- **Stream** — a named, persistent log of messages on matching subjects. Messages survive server restarts.
- **Consumer** — a stateful cursor into a stream. Tracks which messages have been delivered and acknowledged.
- **Pull consumer** — the consumer explicitly calls `fetch()` to pull batches. Best for backpressure control.
- **Ack** — the consumer must acknowledge each message. Unacked messages are redelivered.

### Flow

```
Publisher                      NATS + JetStream               Consumer
   |                              |                              |
   |-- js.publish("orders.created", data) -->|                   |
   |                              |-- persists to stream ORDERS  |
   |                              |                              |
   |                              |              sub.fetch(batch=10) --|
   |                              |-- deliver batch ------------->|
   |                              |                              |-- msg.ack() per message
   |                              |-- marks acked, advances cursor
```

### Code

```python
import nats
from nats.js.errors import NotFoundError

nc = await nats.connect("nats://127.0.0.1:4222")
js = nc.jetstream()

# Create a stream that captures all orders.* subjects
await js.add_stream(name="ORDERS", subjects=["orders.>"])

# Publish events — these are persisted to disk
await js.publish("orders.created", b'{"id": 1, "total": 99.90}')
await js.publish("orders.updated", b'{"id": 1, "status": "paid"}')

# Pull consumer with durable name — survives restarts
sub = await js.pull_subscribe("orders.>", durable="order-processor", stream="ORDERS")

msgs = await sub.fetch(batch=10, timeout=3.0)
for msg in msgs:
    print(f"{msg.subject}: {msg.data.decode()}")
    await msg.ack()  # explicit ack — unacked messages are redelivered
```

**Critical details:**

- `js.add_stream(name, subjects)` — creates the persistent stream. Subjects use the same wildcards as core NATS.
- `js.publish()` returns an ack from the server confirming persistence. Unlike core `nc.publish()`, this is not fire-and-forget.
- `durable="name"` — the consumer position survives disconnects. Without it, the consumer is ephemeral.
- `sub.fetch(batch=N, timeout=T)` — pulls up to N messages, waits up to T seconds. Use `batch` for throughput, `timeout` to avoid blocking forever.
- `msg.ack()` — tells JetStream this message was processed. Without ack, it will be redelivered after `ack_wait` (default 30s).
- In production, set `num_replicas=3` on the stream for HA across a NATS cluster.

---

## 5. KV Store (JetStream)

**What it solves:** distributed key-value store with versioning, history, and real-time watches.

**When to use:** shared configuration, feature flags, service discovery, session state — anything that needs get/put/watch semantics across services. Replaces Redis for simple KV patterns when you already run NATS.

**Key concepts:**

- **Bucket** — a named KV namespace (backed by a JetStream stream internally).
- **Revision** — every put increments a per-key revision number. Enables optimistic concurrency.
- **Watch** — subscribe to real-time changes on a key pattern. Gets notified on put/delete.
- **History** — configurable number of past revisions kept per key.

### Flow

```
Service A                      NATS KV (JetStream)            Service B
   |                              |                              |
   |-- kv.put("config.theme", b"dark") -->|                      |
   |                              |-- stores revision 1          |
   |                              |                              |
   |                              |       kv.watch("config.>") --|
   |                              |-- push update: theme=dark -->|
   |                              |                              |-- react to config change
```

### Code

```python
import nats

nc = await nats.connect("nats://127.0.0.1:4222")
js = nc.jetstream()

# Create bucket with 5 revisions of history per key
kv = await js.create_key_value(bucket="app_config", history=5)

# Put and get
await kv.put("config.api_timeout_ms", b"5000")
entry = await kv.get("config.api_timeout_ms")
print(f"{entry.key} = {entry.value.decode()} (revision {entry.revision})")

# Watch for real-time changes
watcher = await kv.watch("config.>", include_history=False)
async for update in watcher:
    if update is None:
        continue  # initial sync marker
    print(f"changed: {update.key} = {update.value.decode()} rev={update.revision}")
    break  # in production, keep iterating

# Delete and check history
await kv.delete("config.api_timeout_ms")
entries = await kv.history("config.api_timeout_ms")  # list of all revisions
```

**Critical details:**

- `create_key_value(bucket, history=N)` — `history` controls how many past revisions to keep per key. Default is 1 (only latest).
- `kv.get(key)` — returns `Entry` with `.value`, `.revision`, `.created`. Raises `KeyNotFoundError` if missing.
- `kv.put(key, value)` — value is `bytes`. Returns the new revision number.
- `kv.watch(keys)` — `keys` supports wildcards (`>`, `*`). The first `None` entry signals initial sync is done.
- Keys are strings matching `[-/_=.a-zA-Z0-9]+`. Use dots for hierarchy: `config.database.pool_size`.
- KV is built on JetStream streams internally — same persistence, replication, and durability guarantees.

---

## Connection Patterns

### Reconnection (production default)

```python
nc = await nats.connect(
    servers=["nats://nats-1:4222", "nats://nats-2:4222", "nats://nats-3:4222"],
    allow_reconnect=True,           # default: True
    max_reconnect_attempts=60,      # default: 60
    reconnect_time_wait=2,          # seconds between attempts
    error_cb=on_error,
    disconnected_cb=on_disconnect,
    reconnected_cb=on_reconnect,
)
```

### Drain (graceful shutdown)

```python
# Instead of nc.close(), drain finishes in-flight messages then closes
await nc.drain()
```

---

## When to Use Each Pattern

| Pattern       | Delivery      | Persistence | Use Case                                       |
| ------------- | ------------- | ----------- | ---------------------------------------------- |
| Pub/Sub       | at-most-once  | no          | notifications, cache invalidation, telemetry   |
| Request-Reply | at-most-once  | no          | service-to-service RPC, replaces internal HTTP |
| Queue Groups  | at-most-once  | no          | task distribution, load balancing workers      |
| JetStream     | at-least-once | yes (disk)  | event sourcing, order processing, audit logs   |
| KV Store      | at-least-once | yes (disk)  | config, feature flags, shared state            |

---

## What NATS Does NOT Do

**Stream Processing** — NATS delivers events but does not have a built-in DSL for windowed aggregations, joins, or stateful transformations (like Kafka Streams or Flink). You write that logic in your consumer code. NATS handles the transport and persistence; your app handles the computation.
