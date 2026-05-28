# Agent Behavior

## Restrictions

- **NEVER** create `.md`, `.txt`, README, or documentation files unless explicitly requested.
- **NEVER** write tests unless explicitly requested. When asked: `pytest` (Python), `vitest` (TypeScript).
- **Git**: `add/commit/status/diff/log/stash/branch` (listing) sem prompt. `push` SEMPRE confirma antes (mesmo se já mencionado). `rebase/merge/reset --hard/push --force/branch -D/checkout` só com pedido explícito + confirmação. `push --force`, `reset --hard`, `clean -fd` são deny global no settings.
- **NEVER** install packages/dependencies without explicit instruction. Propose first.
- **Surgical edits only.** Change the exact lines necessary. NEVER re-output entire files or refactor unrelated code.
- **`print()` é proibido em Python.** Use `structlog.get_logger(__name__)`. Lint `T20` enforces. Ver `logging.md`.
- Remove `console.log()`, `debugger` antes de finalizar.
- Sem backwards-compat shims, feature flags, ou migration paths quando o user pede mudança direta.

## Communication

- Direto e conciso. Code + 2–4 sentenças max.
- Sem sycophancy/filler ("Here is the updated code", "I understand", "Let me know if...").
- Bug fix → diga o que estava errado, brevemente. Proposal → state o trade-off. Unclear → pergunte uma coisa antes de assumir.
- Flag missed/inconsistent details proactively.
- Code em English (identifiers, comments, docstrings). Chat em pt-BR.

## Skills — When to Invoke

Invoque ANTES de escrever código quando o trigger bate. Não re-derive padrão que a skill encoda. Na dúvida, invoque — falso positivo custa tokens; falso negativo custa correção.

| Trigger                                                                                                                | Skill                             |
| ---------------------------------------------------------------------------------------------------------------------- | --------------------------------- |
| `.sql` migration (CREATE/ALTER), `migrate:up/down`, `DBMATE_*`                                                         | `dbmate`                          |
| Migration nova: `CREATE TABLE`, `CREATE INDEX`, FK, VARCHAR enum-like, GIN em JSONB, UNIQUE com soft delete            | `db-schema-discipline`            |
| Qualquer `*_repository.py`: fetch/fetchrow/fetchval/execute, INSERT/UPDATE/SELECT/DELETE, JSONB, WHERE dinâmico        | `asyncpg-reference`               |
| Qualquer `/auth/*`, refresh_tokens repo, middleware auth, login/logout/refresh, password hashing, Google OAuth, cookie | `auth-hardened`                   |
| Fan-out concorrente, timeout, capacity limiter, memory stream, cancel scope, file I/O em handler async                 | `anyio-concurrency`               |
| Cache TTL, contador, sliding window, rate limit, invalidação event-driven (Valkey/Redis)                               | `valkey-cache`                    |
| Decisão entre NATS/Redis/Kafka/Celery/Temporal; arquitetura event-driven                                               | `distributed-infrastructure`      |
| Pattern NATS (Pub/Sub, Request-Reply, Queue Groups, JetStream, KV)                                                     | `nats-messaging`                  |
| Nova config env-aware, criar `Settings`, nova secret, `compose.override.yaml`, bootstrap inicial                       | `python-config-bootstrap`         |
| Bootstrap structlog, migrar `print()` para logger, configurar request_id                                               | `logging-setup`                   |
| Chamada HTTP de Python (substitui requests/httpx)                                                                      | `http-client`                     |
| Imagem (decode, resize, AVIF, OpenCV)                                                                                  | `image-processing`                |
| PDF (merge, split, render, extract — pikepdf/pypdfium2)                                                                | `pdf-processing`                  |
| QUALQUER upload (arquivo/imagem/doc/mídia/áudio/vídeo/export) em qualquer linguagem/storage                            | **OBRIGATÓRIO** `uploads-storage` |
| Integração Meta (Facebook Login, WhatsApp Cloud, Instagram); webhook Deauth/Data Deletion; HMAC validation             | `meta-app-setup`                  |
| Form async, data fetch fora de TanStack Query, optimistic UI, `useEffect + fetch`/`useEffect + setState`               | `react-19-patterns`               |
| Modal/overlay: Dialog vs Sheet vs Drawer vs Popover; confirm; detail view popup                                        | `dialog-first-overlays`           |
| `useState`/Context/Zustand: onde mora cada state; lifting state; URL vs server vs local                                | `frontend-state-management`       |
| Setup Tailwind, criar/editar `index.css`, OKLCH tokens, container query, migrar Tailwind 3→4                           | `tailwind-4-setup`                |
| Three.js / R3F / shader / scene 3D / particles 3D / GLTF                                                               | `threejs-r3f-patterns`            |
| Shadcn component, Magic UI, Shadcn Charts, registry, preset, `components.json`                                         | `shadcn`                          |
| Landing pública / splash / hero com particles + CTA pra `/login` (rota fora do app shell)                              | `epic-startup-landing`            |
| App shell autenticado (sidebar collapsible-to-icon, breadcrumb, route split público vs `/app`, `useAuth()`)            | `standard-app-shell`              |
| UI com peso estético/de marca — landing, hero, dashboard novo, login flow                                              | `frontend-design`                 |
| "Fica lento depois de X min", "preciso dar F5", memória cresce, CPU alta idle, regressão de performance                | `frontend-performance-ultimate`   |
| Chart matplotlib/seaborn/plotly de Polars/Pandas                                                                       | `data-visualization`              |
| Refactor cirúrgico de código existente (extract, rename, split god class)                                              | `code-refactor`                   |

## Package Managers

- Python: **uv only** (`uv add`, `uv run`, `uv sync`). NEVER pip/poetry/conda.
- TypeScript: **bun only** (`bun add`, `bun dev`, `bun run`). NEVER npm/yarn/pnpm.

## Shell Commands

- **NEVER chain commands** com `&&`, `||`, `;` em uma só Bash call. Cada comando = invocação separada (sistema de permissão casa por string completa).
- **Modern CLI sempre**: `rg` (não grep), `fd` (não find), `bat --paging=never` (não cat), `eza` (não ls), `sd` (não sed), `dust` (não du), `delta` (não diff), `tokei` (não wc -l), `jq` (para JSON).
- Standard build tools (`uv`, `bun`, `cargo`, `make`, `docker compose`, `psql`, `git`, `curl`) pré-allowed. Destrutivas (`rm -rf`, `sudo`, `git push --force`, `docker system prune`) denied — nunca tente.
