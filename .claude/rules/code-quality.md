# Code Quality — Functions, Modules & Boundaries

Princípios para código que LLM lê, edita e mantém. Stack-alvo: Python, Rust, TypeScript, Go, C/C++.

## Função-Primeiro, Classe Quando Justificar

- **Default: funções de módulo + dados** (dataclass, Pydantic, TypedDict, struct, record). Classes só para: (1) container de dados validados, (2) serviço com estado real e ciclo de vida (pool, client, cache, sessão).
- **Argumentos explícitos no callsite.** `process_batch(timeout, max_retries, chunk_size)` com constantes no topo do arquivo > `self._process(...)`. Constantes de módulo são greppáveis globalmente; atributos de `self` somem no escopo da classe.
- **Sem `_private` em Python.** Visibilidade via `__all__` ou ausência de import. Rust (`pub`), Go (capitalização), TS (`export`) já resolvem no nível de módulo — Python segue.
- **Callsites limpos.** `self.config.timeout` > `self._config._timeout`. Se você precisa ler um método para entender o que ele puxa de `self._*`, está mal desenhado — passe como argumento.
- **Evite OOP cerimonial.** Getters/setters triviais, herança por reuso, `AbstractBaseFactoryManager` — sinais de que função livre resolve. Herança só quando subtipo É-UM pai em todo contexto; composição em qualquer outro caso.

## Funções & Arquivos

- **Funções: 4–20 linhas.** Uma coisa por função. Se precisa de "and" para descrever, divide.
- **Arquivos: ≤500 linhas hard limit, 200–300 ideal.** Uma responsabilidade clara.
- **Um nível de abstração por função.** Orquestra OU faz — nunca mistura.
- **Parâmetros: 0–3 ideal.** 4+ → struct/dataclass/interface. Nunca boolean para mudar comportamento — funções separadas ou enums.
- **Pure when possible.** Side effects óbvios pelo nome (`save_`, `send_`, `update_`, `delete_`).

## Names — Greppable & Unique

- **Distintivo, searchable, único.** Se `rg "name"` retorna >5 matches não relacionados, renomeia.
- **BAD:** `data`, `process`, `handler`, `manager`, `service`, `util`, `helper`, `info`, `result`.
- **GOOD:** `UserRegistrationValidator`, `fetch_active_organizations_by_owner`.
- Funções: `action + subject + qualifier`. Booleans: `is_`, `has_`, `should_`, `can_`.
- **NUNCA abrevie.** `token_expiry_default_seconds` > `exp_sec`.

## Types

- Sem `any`, sem `Dict` sem parâmetros, sem função pública sem type.
- Python: type hints em toda função pública. `list[str]`, `X | None`.
- TS: strict mode. `interface` para shapes, `type` para uniões. `unknown` + type guard sobre `any`.
- **Make invalid states unrepresentable.** Literal types, discriminated unions, enums, newtypes.
- Validação só em system boundaries (HTTP input, external APIs, uploads). Funções internas confiam nas signatures.

## Constants & Immutability

- Todo numeric literal, threshold, timeout, limit = `UPPER_CASE` no topo do arquivo ou em config module.
- Inline OK só: `0`, `1`, `-1`, `true`/`false`, `""`. Resto ganha nome.
- **Imutável por default.** `frozen`, `readonly`, `const`, `frozenset`, `tuple`, `as const`.

## Control Flow

- **Guard clauses primeiro.** Happy path no nível base. Early return > nested `if`.
- **Max 2 níveis de indentação** dentro de função.
- `get_*` NÃO produz side effect. Função que muta diz no nome.
- **Fail fast, fail loud.** Estado inválido → erro imediato.
- Nunca engula exceções ou retorne sentinel ambíguo (`-1`, `None` quando há tipo de erro).

## Comments — Provenance, Not Narration

- **Escreva o PORQUÊ, nunca o O QUÊ.** O agent sabe o que `i++` faz; não sabe qual bug `#1234` forçou esta ordem.
- **Capture provenance:** issue numbers, commit SHAs, upstream library bugs, regulatory constraints, production incidents.
- **Docstrings em funções públicas:** uma linha de intenção + um exemplo.
- **Mantenha comments do agent em refactor** — encodam contexto valioso.
- **Delete legends óbvias.** `// increment counter` acima de `i++` desperdiça tokens.

## DRY

- Extrai em função/módulo quando lógica é reusada em **2+ call sites** com mesma semântica.
- **Não over-abstrai.** Três linhas similares > abstração prematura.
- Delete código não usado completamente. Sem `_unused`, sem re-exports, sem `// removed`.

## Errors — Include Context

- **BAD:** `raise ValueError("invalid input")`
- **GOOD:** `raise ValueError(f"invalid input: received {x!r}, expected non-empty string of digits")`
- Sempre inclua: valor ofensor, shape esperado, operação que falhou.

## Architecture — Boundaries & Layers

- **SRP:** um módulo = uma razão para mudar. Split por domínio, não por camada técnica.
- **Dependency direction:** outer depende de inner. Domain logic NÃO importa de infrastructure (DB, HTTP, filesystem, SDK).
- **Layer separation:** `Route → Service → Repository`. Routes = HTTP. Services = business + orquestração. Repositories = data access.
- **Boundaries são interfaces.** Repositories, clients, adapters são contratos. Troca implementação sem tocar business logic.
- **Dependency Injection:** injete via constructor/parameter, não via global imports ou module-level singletons. Wrap third-party libs atrás de interface own-code. **Exceção controlada do projeto:** repository/service singletons no fim do módulo (`user_repository = UserRepository()`) — ver `backend.md > Repository Pattern`. Business logic NÃO usa singleton.
- **Defensive code só quando pedido.** Trust internal code. Validate só em boundaries. Não adicione retry/timeout/circuit-breaker speculativamente.

## Observability & Formatting

Structured JSON logs em boundaries (request in/out, external call in/out, unexpected state). Stack em `logging.md`.
Use o formatter default da linguagem (`ruff`, `prettier`, `cargo fmt`, `gofmt`). Não discute estilo.

## What Code Quality Is NOT

- NOT comments excessivos em toda função.
- NOT wrapping todo bloco de 3 linhas em helper.
- NOT pattern collection (factory/builder/observer onde função simples basta).
- NOT premature abstraction para "future flexibility".
- NOT microservices onde module boundary basta.
- NOT reducing line count à custa de legibilidade.

**Alvo: código que lê como prosa bem escrita. Boundaries explícitas, dependency graph limpo, swap de implementação = mudança em 1 arquivo.**
