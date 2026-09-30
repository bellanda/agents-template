<!-- GERADO por rules.py (Config Files/agents) a partir de .claude/rules/*.md — não editar à mão.
     Lido pelo Codex e OpenCode. Claude Code lê .claude/rules/ direto. Skills: .agents/skills/ (Codex)
     e .claude/skills/ (Claude/OpenCode) — mesmo conteúdo. -->

# Project Rules

## Rules por área — LEIA o arquivo antes de criar/editar arquivos que casam os globs

| Rule | Quando ler (globs) | Assunto |
| ---- | ------------------ | ------- |
| `.claude/rules/backend.md` | `backend/**`, `**/*.py`, `config/app/**`, `config/docker/**`, `**/compose*.yaml` | Backend — Python Stack & Invariants |
| `.claude/rules/frontend.md` | `frontend/**`, `config/nginx/**` | Frontend — TypeScript, React, TanStack & Architecture |
| `.claude/rules/logs.md` | `**/*.py` | Logging |
| `.claude/rules/tests.md` | `**/tests/**`, `**/test_*.py`, `**/conftest.py`, `**/*.test.{ts,tsx}`, `**/__tests__/**`, `**/e2e/**`, `**/playwright.config.*`, `**/src/test/**` | Backend Testing |
| `.claude/rules/uploads.md` | `backend/**`, `**/*upload*`, `**/*storage*` | Uploads & Storage — Invariantes |

Skills (checklist + references profundas): `.agents/skills/<nome>/SKILL.md` (mesmo conteúdo de `.claude/skills/`). Invoque a skill do domínio antes de escrever código nele.

# Code Quality — Functions, Modules & Boundaries

Princípios para código que LLM lê, edita e mantém. Stack-alvo: Python, Rust, TypeScript, Go, C/C++.

## Função-primeiro, classe quando justificar

- **Default: funções de módulo + dados** (dataclass, Pydantic, TypedDict, struct, record). Classe só para: container de dados validados, OU serviço com estado real (pool, client, cache, sessão).
- **Argumentos explícitos no callsite.** `process(timeout, max_retries, chunk_size)` com constantes UPPER_CASE no topo do arquivo > `self._process(...)` (atributos somem no escopo da classe).
- **Sem `_private` em Python.** Visibilidade via `__all__` ou ausência de import. Rust/Go/TS já resolvem no nível de módulo.
- **Evite OOP cerimonial.** Getters/setters triviais, herança por reuso, `AbstractBaseFactoryManager` → função livre resolve. Herança só quando subtipo É-UM pai em todo contexto; senão composição.

## Funções & arquivos

- **Funções 4–20 linhas.** Uma coisa. Se precisa de "and" pra descrever, divide.
- **Arquivos ≤500 linhas hard limit, 200–300 ideal.** Uma responsabilidade.
- **Um nível de abstração por função.** Orquestra OU faz — nunca mistura.
- **Parâmetros 0–3 ideal.** 4+ → struct/dataclass/interface. NUNCA boolean para mudar comportamento — funções separadas ou enums.

## Names — greppable & unique

- Distintivo, searchable, único. Se `rg "name"` retorna >5 matches não relacionados, renomeia.
- **BAD**: `data`, `process`, `handler`, `manager`, `service`, `util`, `helper`, `info`, `result`.
- **GOOD**: `UserRegistrationValidator`, `fetch_active_organizations_by_owner`.
- Funções: `action + subject + qualifier`. Booleans: `is_`, `has_`, `should_`, `can_`. NUNCA abrevie.

## Types

- Sem `any`, sem `Dict` sem parâmetros, sem função pública sem type.
- Python: type hints em toda função pública. `list[str]`, `X | None`.
- TS: strict mode. `interface` para shapes, `type` para uniões. `unknown` + type guard sobre `any`.
- **Make invalid states unrepresentable** — literal types, discriminated unions, enums, newtypes.
- Validação só em system boundaries (HTTP input, external APIs, uploads). Funções internas confiam nas signatures.

## Constants & immutability

- Todo literal numérico/threshold/timeout/limit = `UPPER_CASE` no topo do arquivo ou em config module.
- Inline OK só: `0`, `1`, `-1`, `true`/`false`, `""`. Resto ganha nome.
- **Imutável por default**: `frozen`, `readonly`, `const`, `frozenset`, `tuple`, `as const`.

## Control flow

- **Guard clauses primeiro.** Happy path no nível base. Early return > nested `if`.
- **Max 2 níveis de indentação** dentro de função.
- `get_*` NÃO produz side effect. Função que muta diz no nome.
- **Fail fast, fail loud.** Estado inválido → erro imediato.
- Nunca engula exceções ou retorne sentinel ambíguo (`-1`, `None` quando há tipo de erro).

## Comments — contexto para o próximo agente

O usuário não lê código; quem lê é o próximo agente. Comentário bom poupa redescoberta.

- Escreva o **PORQUÊ**, nunca o O QUÊ: regra de negócio, invariante, acoplamento não óbvio, limite externo (API, plataforma, lei), e provenance (issue, commit SHA, bug upstream, incidente, decisão do usuário com data).
- **Docstring de módulo** (1–3 linhas) em arquivo não trivial: responsabilidade + onde se encaixa no fluxo. Docstring em função pública: intenção + (se útil) exemplo.
- Mantenha comments do agent em refactor — encodam contexto valioso. Ao mudar o comportamento, **atualize o comentário junto**; comentário falso é pior que nenhum.
- Delete legends óbvias (`// increment counter` acima de `i++` desperdiça tokens).

## DRY

- Extrai em função/módulo quando lógica é reusada em **2+ call sites** com mesma semântica.
- Não over-abstrai — três linhas similares > abstração prematura.
- Delete código não usado completamente. Sem `_unused`, sem re-exports vazios, sem `// removed`.

## Errors — include context

```
BAD:  raise ValueError("invalid input")
GOOD: raise ValueError(f"invalid input: received {x!r}, expected non-empty string of digits")
```

Sempre inclua: valor ofensor, shape esperado, operação que falhou.

## Architecture

- **SRP** + dependency direction outer→inner. Domain logic NÃO importa infrastructure (DB/HTTP/filesystem/SDK).
- **Layers**: `Route(HTTP) → Service(business) → Repository(data)`. Boundaries são interfaces — troca de implementação sem tocar business.
- **DI via constructor/parameter**, não via global imports. Exceção controlada: repository/service singletons no fim do módulo (vide gate `database`). Business logic NÃO usa singleton.
- **Defensive code só quando pedido.** Trust internal code. Validate só em boundaries. Sem retry/timeout/circuit-breaker speculativo.
- Refactor cirúrgico de código existente → skill `refactor`.

## Formatter

Default da linguagem (`ruff`, `prettier`, `cargo fmt`, `gofmt`). Não discute estilo.

**Alvo: código que lê como prosa. Boundaries explícitas, dependency graph limpo, swap de implementação = mudança em 1 arquivo.**

# Project — Contexto Local

> Rule LOCAL deste projeto (não vem do catálogo central; `rules.py` preserva). Descreva aqui o que
> é específico e não-derivável do código: domínio, decisões fixas, convenções próprias, integrações
> ativas, comandos de build/test, gotchas. Mantenha curto — invariantes de stack já vêm das rules
> do catálogo (`backend.md`, `frontend.md`, `cleancode.md`, `logs.md`, `tests.md`, `uploads.md`).

## O que é

<!-- 1-3 linhas: que produto é, qual o core do domínio. -->

## Decisões fixas (não re-derivar)

<!-- Escolhas já tomadas que o agente deve respeitar sem reabrir. -->

## Comandos

<!-- build / test / lint / migrate específicos deste repo. -->
