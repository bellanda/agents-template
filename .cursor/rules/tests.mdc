# Backend Testing

> Aplica-se **quando o user pede** para escrever/rodar testes ou para criar regression test do bug que está sendo corrigido. Não escreva testes especulativos (ver `agent-behavior.md > Restrictions`).

## Agent-runnable first

- Suite roda com **um comando documentado** (`uv run pytest`, `make test`). Sem seed manual, sem credentials escondidos, sem prompt interativo.
- Output parseável: pass/fail no stdout. Sem TTY dependency.
- Setup novo → documenta em `CLAUDE.md`/`AGENTS.md`/`README.md` do projeto.

## F.I.R.S.T

**Fast** (segundos) | **Independent** (qualquer ordem passa via rollback ou DB ephemeral) | **Repeatable** (determinístico — unique data para `UNIQUE` fields) | **Self-validating** (assertions explícitas, sem "olha o log") | **Timely** (junto com o código — bug fix = regression test).

## Scope

- **Integration-first via HTTP.** Testa comportamento observável pelo public interface.
- **Unit tests só para lógica pura, sem I/O.** Se integration cobre, não duplica.
- **DB de teste real** para persistência/queries/transactions/constraints/serialization/permissions. NUNCA mock DB.
- Reutiliza fixtures shared (client, auth, base data). Sem recriar setup pesado por arquivo.

## Structure

- Arquivos `test_*.py`, funções `test_*`, classes `Test*` só para agrupar flow/resource.
- Arrange / Act / Assert minimalista. Direct assertions.
- Validação em ordem: `status_code` → main response body → side effects persistidos.

## Coverage por rota (mínimo)

| Caso                                       | Status             |
| ------------------------------------------ | ------------------ |
| Success path                               | 200/201            |
| Auth ausente/inválido                      | 401 (se aplicável) |
| Permissão insuficiente                     | 403 (se aplicável) |
| Resource não encontrado                    | 404 (se aplicável) |
| Payload inválido / business rule violation | 400 / 409 / 422    |
| Empty result em list/search                | 200 + empty list   |

## Assertions — business outcomes

- Confirme business outcomes: status transitions, dados criados/updated, history, calculations, permissions, associations.
- **Nunca valide só formato.** "Response tem chave `users`" não é teste.
- Verifique error messages/codes no nível necessário para proteger o contrato. Não acople em texto frágil.
- Garanta que campos sensíveis nunca vazam (passwords, hashes, private tokens, internal secrets).
