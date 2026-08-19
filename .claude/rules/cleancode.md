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

## Comments — provenance, not narration

- Escreva o **PORQUÊ**, nunca o O QUÊ. Capture provenance: issue numbers, commit SHAs, upstream bugs, regulatory constraints, production incidents.
- Docstrings em funções públicas: uma linha de intenção + (se útil) um exemplo.
- Mantenha comments do agent em refactor — encodam contexto valioso.
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
