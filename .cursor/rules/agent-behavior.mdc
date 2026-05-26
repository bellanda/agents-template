# Agent Behavior

## Restrictions

- **NEVER** create `.md`, `.txt`, README, or documentation files unless explicitly requested.
- **NEVER** write tests unless explicitly requested. When asked: `pytest` (Python), `vitest` (TypeScript).
- **Git policy:**
  - **Sem prompt** (sempre permitido): `git add`, `git commit`, `git status`, `git diff`, `git log`, `git stash`, `git branch` (listing).
  - **Com confirmação explícita do user** (mesmo se ele já tiver mencionado antes — sempre confirmar antes do `push`): `git push`.
  - **Só se o user pedir explicitamente, e ainda assim com confirmação:** `git rebase`, `git merge`, `git reset --hard`, `git push --force`, `git branch -D`, `git checkout` (trocar branch — não confundir com `git checkout -- <file>` para descartar mudanças locais, que também é destrutivo e proibido), `git clean -fd`.
  - **Sempre proibido** (settings deny): `git push --force/-f`, `git reset --hard`, `git clean -fd`.
- **NEVER** install packages/dependencies without explicit instruction. Propose first.
- **Surgical edits only.** Change the exact lines necessary. NEVER re-output entire files or refactor unrelated code.
- **`print()` is forbidden in Python code.** Use `structlog.get_logger(__name__)`. Lint `T20` (flake8-print) enforces it. See `logging.md`.
- Remove `console.log()`, `debugger` before finishing any task.
- Do not add backwards-compatibility shims, feature flags, or migration paths when the user asks for a direct change.

## Communication

- Direct and concise. Code + 2–4 sentences max.
- No sycophancy or filler. No "Here is the updated code", "I understand", "Let me know if you need anything else".
- Bug fix → state what was wrong, briefly. Proposal → state the trade-off. Unclear → ask one question before assuming.
- Flag missed or inconsistent details proactively.
- Code in English (identifiers, comments, docstrings). Chat in Portuguese (pt-BR).

## Skills — When to Invoke

Invoque ANTES de escrever código quando o trigger bate. Não re-derive padrão que a skill encoda. Se o trigger é ambíguo, invoque — falso positivo custa tokens; falso negativo custa correção.

| Trigger no código / pedido                                                                    | Skill                                                                                                                      |
| --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| muda schema (nova coluna/tabela/constraint, alteração de model entidade ↔ tabela), cria/roda/rollback `.sql` migration, `migrate:up`, `DBMATE_*` | `dbmate`                                                                                                                   |
| escreve / revisa query asyncpg, escolhe entre fetch/fetchrow/fetchval/execute                 | `asyncpg-reference`                                                                                                        |
| toca `/auth/*`, refresh repository, middleware auth, login/logout/refresh, Argon2, Google OAuth, cookie de auth | `auth-hardened`                                                                                                            |
| escreve fan-out concorrente, timeout, capacity limiter, memory stream, cancel scope, ou file I/O em handler async | `anyio-concurrency`                                                                                                        |
| inicia projeto novo, padroniza logs, migra `print()` para logger, configura request_id        | `logging-setup`                                                                                                            |
| chamada HTTP de Python (substitui requests/httpx)                                             | `http-client`                                                                                                              |
| processa imagem (decode, resize, AVIF, OpenCV)                                                | `image-processing`                                                                                                         |
| mexe em PDF (merge, split, render, extract, pikepdf, pypdfium2)                               | `pdf-processing`                                                                                                           |
| adiciona/remove/debuga shadcn component, registry, preset, Magic UI                           | `shadcn`                                                                                                                   |
| cria gráfico (line/bar/area/pie) em projeto React                                             | `shadcn` (sub-rule `charts.md`)                                                                                            |
| escreve/refactora form async, data fetch fora de TanStack Query, optimistic UI, ou `useEffect` que faz fetch / deriva state | `react-19-patterns`                                                                                                        |
| cria UI com peso estético/de marca — landing, hero, dashboard novo, login flow, scene 3D     | `frontend-design`                                                                                                          |
| cria landing pública / splash / hero com particles + CTA pra `/login` (rota fora do app shell) | `epic-startup-landing`                                                                                                     |
| scaffold app shell autenticado (sidebar collapsible-to-icon, breadcrumb header, route split público vs `/app`, `useAuth()`) | `standard-app-shell`                                                                                                       |
| escreve/integra Three.js / R3F / shaders / scene 3D                                          | `frontend-design` + `ui-ux-pro-max` (referência `data/stacks/threejs.csv`)                                                |
| usuário relata "fica lento depois de X min", "preciso dar F5", memória cresce, CPU alta idle  | `frontend-performance-ultimate`                                                                                            |
| escolhe NATS vs Redis vs Kafka vs Celery vs Temporal, desenha event-driven                    | `distributed-infrastructure`                                                                                               |
| implementa pattern NATS (Pub/Sub, JetStream, KV, Queue Groups)                                | `nats-messaging`                                                                                                           |
| escreve / revisa código que usa Valkey/Redis (cache, contadores, sliding window, invalidação) | `valkey-cache`                                                                                                             |
| refactor cirúrgico de código existente (extract, rename, split god class)                     | `code-refactor`                                                                                                            |
| chart matplotlib/seaborn/plotly de Polars/Pandas                                              | `data-visualization`                                                                                                       |
| **QUALQUER upload** (arquivo/imagem/doc/mídia/áudio/vídeo/export) em qualquer linguagem (Python/Rust/Go) e storage (local/B2/S3/Azure/GCS), nova `kind`, modelagem entity+file | **OBRIGATÓRIO** `uploads-storage` ANTES de codar — não opcional, não re-derivar (complementa rule `uploads.md`)                                                                          |
| adiciona/altera config (env-aware) — postgres, cors, valkey, nats, granian etc                | edita TODOS os 3 `config/app/{env}.yaml` + sub-model em `config/settings.py`. Ver `backend.md > Environment & Config`. |
| adiciona nova secret obrigatória                                                              | adiciona em `.env.example` (vazia) + field `SecretStr` em `Settings`. NUNCA commit valor real.                             |

## Package Managers

- Python: **uv only** (`uv add`, `uv run`, `uv sync`). NEVER pip/poetry/conda.
- TypeScript: **bun only** (`bun add`, `bun dev`, `bun run`). NEVER npm/yarn/pnpm.

## Shell Commands

- **NEVER chain commands** com `&&`, `||`, ou `;` em uma só Bash call. Cada comando = invocação separada. O sistema de permissão casa por string completa — comando composto bypassa allow rules e dispara confirmação.
- Always use modern CLI tools over classic equivalents:

| Use this              | NOT this                    | Why                                                                 |
| --------------------- | --------------------------- | ------------------------------------------------------------------- |
| `rg` (ripgrep)        | `grep`                      | Faster, respects `.gitignore`, skips `node_modules`/`target`/`.git` |
| `fd`                  | `find`                      | Simpler syntax, respects `.gitignore`, parallel execution           |
| `bat --paging=never`  | `cat`                       | Syntax highlight, line numbers (always `--paging=never` em scripts) |
| `eza`                 | `ls`                        | Aliased com `--icons`, `--git`, `--group-directories-first`         |
| `sd 'old' 'new' file` | `sed -i 's/old/new/g' file` | Literal strings by default, sem escape hell                         |
| `dust`                | `du`                        | Visual tree sorted by size (aliased as `du`)                        |
| `delta`               | `diff`                      | Side-by-side, syntax-aware (configured as Git pager)                |
| `tokei`               | `wc -l` / `cloc`            | Lines of code per language                                          |
| `jq`                  | manual JSON parsing         | Pipe-friendly JSON processing                                       |

Standard build tools (`uv`, `bun`, `cargo`, `make`, `docker compose`, `psql`, `git`, `curl`, etc.) são pre-allowed globalmente. Operações destrutivas (`rm -rf`, `sudo`, `git push --force`, `docker system prune`) são denied — nunca tente.
