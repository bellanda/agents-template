# Backend Testing

> Aplica-se **quando o user pede** para escrever/rodar testes ou quando você precisa criar regression test para bug que está corrigindo. Não escreva testes especulativos (ver `agent-behavior.md > Restrictions`).

## Agent-Runnable First

- Suite roda com **um comando documentado** (`uv run pytest`, `make test`) — sem seed manual, sem credentials escondidos, sem prompt interativo.
- Output parseável: pass/fail no stdout. Sem TTY dependency.
- Setup novo? Documenta no `CLAUDE.md` / `AGENTS.md` / `README.md` do projeto. Setup não-documentado = agent não roda = feedback loop quebra.

## F.I.R.S.T

- **Fast** — segundos, não minutos.
- **Independent** — cada teste isola seu state via transactional rollback ou DB ephemeral. Qualquer ordem passa.
- **Repeatable** — determinístico. Use unique data para `UNIQUE` fields; nunca valores fixos que colidem entre runs.
- **Self-validating** — assertions explícitas. Sem "olha o log pra ver se deu certo".
- **Timely** — junto com o código. Função nova → teste novo. Bug fix → regression test.

## Scope

- **Integration-first via HTTP.** Testa comportamento observável e business rules pelo public interface.
- **Unit tests só para lógica pura, sem I/O.** Se integration cobre, não duplica.
- **DB de teste real** para tudo com persistência, queries, transactions, constraints, serialization, permissions. NUNCA mock DB.
- Reutiliza fixtures shared (client, auth, base data). Não recria setup pesado por arquivo.

## Structure

- Arquivos `test_*.py`, funções `test_*`, classes `Test*` só para agrupar flow/resource.
- Arrange / Act / Assert minimalista. Direct assertions.
- Validação em ordem: `status_code` → main response body → side effects persistidos.

## Coverage Contract per Route

Mínimo para toda rota nova:

- Success path.
- Auth ausente/inválido → `401` (quando aplicável).
- Permissão insuficiente → `403` (quando aplicável).
- Resource não encontrado → `404` (quando aplicável).
- Payload inválido / business rule violation → `400` / `409` / `422` (quando relevante).
- Empty result em list/search — empty list não é erro.

## Assertions — Business Outcomes, Not Format

- Confirme business outcomes: status transitions, dados criados/updated, history, calculations, permissions, associations.
- **Nunca valide só formato.** "Response tem chave `users`" não é teste.
- Verifique error messages/codes no nível necessário para proteger o contrato. Não acople em texto frágil.
- Garanta que campos sensíveis nunca vazam (passwords, hashes, private tokens, internal secrets).
