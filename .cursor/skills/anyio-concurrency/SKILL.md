---
name: anyio-concurrency
description: Structured concurrency Python com anyio — task groups, timeouts, capacity limiters, memory streams, cancel scopes, shielding, ExceptionGroup. INVOCAR ANTES de escrever ou refatorar código async que faça fan-out de N tasks, precise de timeout, queue entre tasks, limite de concorrência, file I/O em handler async, subprocess, ou cleanup crítico que precisa sobreviver a cancelamento. Substitui qualquer pattern asyncio direto (`asyncio.gather`, `asyncio.create_task`, `asyncio.wait_for`, `asyncio.Queue`, `asyncio.Lock`) — anyio é o default cross-projeto. Não invocar para um único await sequencial; só quando há concorrência real.
---

# anyio — Structured Concurrency

Default cross-projeto: **anyio** (não asyncio puro). Trabalho concorrente vive sempre dentro de um escopo (`async with anyio.create_task_group():`); quando o bloco fecha, todas as tasks terminaram, foram canceladas, ou propagaram erro. Zero task zombie.

## Tabela de substituição

| Caso                                                 | Use                                           | NUNCA                                     |
| ---------------------------------------------------- | --------------------------------------------- | ----------------------------------------- |
| Fan-out N tasks                                      | `anyio.create_task_group()` + `tg.start_soon` | `asyncio.gather` (zombie tasks em falha)  |
| Timeout                                              | `anyio.fail_after(s)` / `move_on_after(s)`    | `asyncio.wait_for`                        |
| Limitar concorrência                                 | `anyio.CapacityLimiter(N)`                    | semáforo manual                           |
| Comunicar entre tasks                                | `anyio.create_memory_object_stream[T]()`      | `asyncio.Queue`                           |
| Lock/Event/Semaphore                                 | `anyio.Lock` / `Event` / `Semaphore`          | `asyncio.Lock` (não respeita CancelScope) |
| Sync bloqueante (Polars, OpenCV, pikepdf, RapidFuzz) | `await anyio.to_thread.run_sync(fn, *args)`   | chamada direta (bloqueia loop)            |
| File I/O em handler async                            | `await anyio.Path(p).read_text()`             | `open(p).read()`                          |
| Subprocess                                           | `await anyio.run_process([...])`              | `subprocess.run`                          |
| Sleep                                                | `await anyio.sleep(s)`                        | `time.sleep`                              |
| Background fora do request                           | NATS consumer / Celery / queue persistente    | `asyncio.create_task` em handler          |

## Padrão canônico — fan-out com slot pré-alocado

```python
async def fetch_many(urls: list[str]) -> list[dict]:
    results: list[dict | None] = [None] * len(urls)

    async def _fetch(slot: int, url: str) -> None:
        results[slot] = await http.get_json(url)

    async with anyio.create_task_group() as tg:
        for slot, url in enumerate(urls):
            tg.start_soon(_fetch, slot, url)

    return [r for r in results if r is not None]
```

Slot pré-alocado preserva ordem sem `gather`'s overhead de coleta. Falha de qualquer task cancela as outras e propaga `ExceptionGroup`.

## Timeouts

```python
# Hard timeout — levanta TimeoutError
async with anyio.fail_after(10):
    result = await slow_op()

# Soft timeout — segue em frente após N segundos sem levantar
async with anyio.move_on_after(10) as scope:
    result = await slow_op()
if scope.cancel_called:
    log.warning("op_timeout")
    result = None
```

`anyio.fail_after` respeita CancelScope corretamente; `asyncio.wait_for` tem race condition documentada quando combinado com outros scopes.

## Concorrência limitada — CapacityLimiter

```python
async def crawl_with_limit(urls: list[str], max_inflight: int = 10) -> list[dict]:
    limiter = anyio.CapacityLimiter(max_inflight)
    results: list[dict | None] = [None] * len(urls)

    async def _one(slot: int, url: str) -> None:
        async with limiter:
            results[slot] = await http.get_json(url)

    async with anyio.create_task_group() as tg:
        for slot, url in enumerate(urls):
            tg.start_soon(_one, slot, url)

    return [r for r in results if r is not None]
```

Crawler com 1000 URLs e `max_inflight=10` mantém 10 simultâneas máximo, sem queue manual.

## Memory streams — comunicação tipada entre tasks

```python
send, receive = anyio.create_memory_object_stream[dict](max_buffer_size=100)

async def producer() -> None:
    async with send:
        for item in source:
            await send.send(item)

async def consumer() -> None:
    async with receive:
        async for item in receive:
            await process(item)

async with anyio.create_task_group() as tg:
    tg.start_soon(producer)
    tg.start_soon(consumer)
```

`max_buffer_size=100` faz backpressure: producer espera quando cheio. Producer-consumer fan-out sem `asyncio.Queue` (que não tem tipagem genérica nem integração com cancel scopes).

## Sync bloqueante em handler async

```python
# Polars, OpenCV, pikepdf, RapidFuzz, NumPy — operações CPU-bound não async.
df = await anyio.to_thread.run_sync(
    lambda: pl.scan_parquet(path).filter(pl.col("x") > 0).collect()
)

# Função com args explícitos (preferido vs lambda quando args são serializáveis)
result = await anyio.to_thread.run_sync(cv2.imdecode, buffer, cv2.IMREAD_COLOR)
```

`anyio.to_thread.run_sync` libera o loop event durante a chamada bloqueante. Default thread pool é compartilhado; para isolamento crítico, criar `anyio.from_thread.BlockingPortal` próprio.

## Cancelamento — finally + shield

```python
async def with_cleanup(conn) -> Result:
    try:
        await conn.execute("BEGIN")
        result = await do_work(conn)
        await conn.execute("COMMIT")
        return result
    except BaseException:
        with anyio.CancelScope(shield=True):
            # Cleanup crítico sobrevive a cancelamento externo.
            await conn.execute("ROLLBACK")
            await conn.close()
        raise
```

`CancelledError` (anyio: `anyio.get_cancelled_exc_class()`) é "pare e libere recursos" — NUNCA engula com `except Exception: pass`. Cleanup vai em `finally`; se precisa sobreviver a cancelamento externo (timeout do parent), envolva em `CancelScope(shield=True)`.

## ExceptionGroup — múltiplas falhas

Quando várias tasks dentro de um task group falham, todas as exceções chegam num `ExceptionGroup` (PEP 654). Trate por tipo com `except*`:

```python
try:
    async with anyio.create_task_group() as tg:
        tg.start_soon(maybe_fail_a)
        tg.start_soon(maybe_fail_b)
        tg.start_soon(maybe_fail_c)
except* ValueError as eg:
    for exc in eg.exceptions:
        log.exception("value_error", error=str(exc))
except* ConnectionError as eg:
    log.error("connection_failed", count=len(eg.exceptions))
```

Sem `except*`, um `try: ... except ValueError` só pega `ExceptionGroup` em si — você perde acesso à lista individual.

## Background tasks — não use `create_task` em handler

```python
# ❌ Errado: task fica órfã, sem cleanup, sem error propagation
@app.post("/send-notification")
async def send_notification(payload: NotificationIn):
    asyncio.create_task(notify_external(payload))   # fire-and-forget perigoso
    return {"status": "queued"}

# ✅ Certo: empilhar em NATS / Celery / queue persistente
@app.post("/send-notification")
async def send_notification(payload: NotificationIn, nats: NatsClient = Depends(...)):
    await nats.publish("notifications.send", orjson.dumps(payload.model_dump()))
    return {"status": "queued"}
```

Background no mesmo processo = perda silenciosa de tasks no shutdown, sem retry, sem observabilidade. Se realmente precisa de side task curta dentro do request lifecycle, use `BackgroundTasks` do FastAPI (que roda DEPOIS da response e tem cleanup integrado).

## Don'ts

- **NUNCA** `asyncio.gather` — task zombie em falha, sem cancelamento estruturado.
- **NUNCA** `asyncio.create_task(...)` solto em handler — task órfã sem cleanup.
- **NUNCA** `asyncio.wait_for` — race condition com cancel scopes. Use `anyio.fail_after`.
- **NUNCA** `asyncio.Lock` / `asyncio.Queue` em código novo — usar versões `anyio.*`.
- **NUNCA** `time.sleep` em código async. `anyio.sleep`.
- **NUNCA** `open(path)` ou `subprocess.run` em handler async. `anyio.Path` / `anyio.run_process`.
- **NUNCA** engulir `CancelledError` com `except Exception` ou `except BaseException: pass`.
- **NUNCA** chamar Polars/OpenCV/pikepdf direto no event loop. `anyio.to_thread.run_sync`.
- **NUNCA** assumir que falha de uma task cancela só ela — task group cancela TODAS.
