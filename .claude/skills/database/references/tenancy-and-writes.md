# Tenancy, escrita concorrente e conexão — regras de backend da frota

> Reference do gate `database`. Origem: auditoria da frota 2026-11-13 (rodada de correção). Cada
> bloco é uma regra + o porquê + o helper canônico. Guardas executáveis em `references/tenancy/`
> (copiadas sem edição, à mão — o `rules.py` não as propaga — para todo backend
> multi-tenant): `test_tenancy_guard.py`, `test_client_ip_guard.py`, `test_streaming_routes_no_get_conn.py`.
> `test_tenancy_guard.py` NÃO vai para app sem `organization_id` no schema (optimuslar: dono por usuário,
> `realtor_id`/`owner_user_id`): o teste dá SKIP (nunca PASS silencioso) se o schema não tem tabela de tenant (caso do template-base).

## 1. Tenancy — todo id que chega é provado antes do uso

- **Todo SQL do backend** (repository, service, rota, consumer, agente, cron, pipeline, script):
  leitura/UPDATE/DELETE em tabela com `organization_id` filtra por ele.
  `WHERE id = $1` sozinho é IDOR clássico: passa em todo teste com 1 org e vaza loja alheia em prod.
  "A rota já conferiu" NÃO dispensa o filtro quando a org está à mão: defesa em profundidade.
  `tests/test_tenancy_guard.py` reprova (varre todo `.py` de `src`/`cron`/`pipelines`/`agents`/
  `scripts` desde 2026-11-14; antes só `*_repository.py`, e SQL em service/cron ficava invisível).
- **`organization_id` só conta como PREDICADO**: listado no SELECT ou no RETURNING não é filtro.
- **Tabela-filha** (sem `organization_id`, pendurada por FK direta ou transitiva em tabela de
  tenant: itens de pedido, fotos, membros de fila, destinatários de campanha): a instrução carrega
  a checagem da org ela mesma, com JOIN ou `EXISTS` no ancestral, sem ida extra ao banco (a PK do
  pai resolve). INSERT em filha com id do pai vindo de fora vira
  `INSERT … SELECT … WHERE EXISTS (pai na org)` e o chamador trata "nenhuma linha".
- **Marca `tenant-ok: <motivo>`** só quando nenhuma org se aplica, e o motivo NOMEIA a entrada:
  cron/varredura de plataforma (qual job), rota pública por slug/token (o token É o escopo),
  webhook que resolve o tenant por id externo, rota de superusuário, lookup pré-login, script de
  operador. Função que só tem o id por vir de consumer/webhook chama-se `..._for_consumer` /
  `..._for_webhook`; loader por usuário `..._for_user`. Não existe marca genérica: `baseline`
  (dívida de 2026-11-13) foi conferida uma a uma e eliminada em 2026-11-14 nos 7 repos.
- **Limites conhecidos da trava** (levam marca com o motivo): coluna de tenant com outro nome
  (`organizer_organization_id`, `timing_organization_id`), escopo por usuário, CTE com o mesmo nome
  da tabela.
  Leitura "by-id" que serve OUTRA entidade (`get_by_vehicle_id`) também recebe `organization_id`.
- **Id vindo de body/path/query** (`vehicle_id`, `contact_id`, `customer_id`, `user_id`, URL de
  upload) é provado dentro da org do chamador ANTES de gravar/usar, por helper compartilhado
  `ensure_<entidade>_in_org` / `assert_<entidade>_in_org` (promoservice
  `services/organizations/org_references.py`; kailos `ensure_contact_in_org`,
  `assert_active_member`). FK do banco é simples (`id`), então UUID de outra loja passa na
  constraint. `users` é tabela GLOBAL: pertencer à org = checar `organization_members`. Cross-org
  responde 400/404 igual ao inexistente.
- **Flags de plataforma** (`organizations.is_active`, plano, limites) nunca entram em payload
  editável pelo tenant. Transição de estado (fechar/cancelar) é compare-and-set sob `FOR UPDATE`
  numa transação.
- **Último gestor**: a trava "não remova o último manager" vale para REMOVER e para trocar papel.
- **Delete de X** checa dependentes vivos (pedidos abertos, orçamentos, recebíveis) e devolve 409
  que NOMEIA o que bloqueia (promoservice `services/organizations/dependents_guard.py`
  `ensure_no_active_dependents`); vale para delete de cliente/veículo/contato nos outros apps.
- **Dado sensível por papel** (custo) é redigido em TODA rota que serializa a entidade, não só na
  tela que motivou; um helper `redact` ao lado de `can_read_costs`.
- **Cron por org**: loop por organização com `try/except` e `logger.exception(org_id)`; dashboard em
  cache mantém dado "de agora" (contadores, pedido parado) fora do corpo cacheado.
- **IP do cliente** só por `client_ip()` (`core/client_ip.py`: `X-Real-IP` do nginx; sem ele, o
  ÚLTIMO elemento de `X-Forwarded-For`, anexado pelo nginx; o primeiro é do cliente e NUNCA é
  usado) ou `request_evidence()`. `tests/test_client_ip_guard.py` reprova ler `X-Forwarded-For`
  em outro lugar (promoservice gravava o 1º elemento como evidência legal de aprovação).
- Modo de carrinho/consulta que busca terceiro por CPF exige relacionamento aceito, responde igual
  para CPF desconhecido e não vinculado, e limita tentativas falhas por usuário.

## 2. Escrita concorrente — `get_conn` é autocommit

- **Ledger + saldo** (linha de lançamento + saldo) ficam no MESMO `conn.transaction()` com a linha
  de saldo travada (`SELECT … FOR UPDATE`) ANTES de validar o débito. Sem isso, duas requisições
  passam pela validação e estouram o saldo.
- **Baixa/pagamento**: trava a conta-mãe e depois a parcela (`FOR UPDATE`), na mesma transação;
  limite no próprio UPDATE (`SET paid = paid + $n WHERE paid + $n <= amount`) e `CHECK
  (paid_amount <= amount)` como última linha de defesa.
- **Operação de dinheiro em autocommit** (inscrições→pagamentos): abra a transação ANTES do `FOR
  UPDATE` (fora dela o lock some ao fim do statement).
- **Varredura que engole exceção** precisa de backoff persistido + lista de exclusão por ciclo;
  uma linha envenenada senão trava a fila inteira. `agent_*` tem trigger BEFORE UPDATE que reseta
  `updated_at`: teste que precisa de `updated_at` antigo usa `session_replication_role = replica`
  (`tests/helpers/aging.py`).
- **Lista JSONB acrescentada por handler de upload** é relida `FOR UPDATE` DEPOIS da escrita lenta
  no storage, nunca antes (dois uploads simultâneos perdiam um item).
- **Lease de cron** (`ad_accounts.synced_at`, `external_sources.synced_at`) é escrito só pelo cron;
  claim/refresh de snapshot não escreve nele.
- **Todo caminho que fecha acesso** (desconectar, desautorizar, desativar, liberar, apagar) libera
  os claims e cancela `agent_actions` abertas.
- **Efeito colateral de rota/serviço dentro de transação** (portal, fila, cache, SSE, apagar
  arquivo) roda DEPOIS do COMMIT: lista `after_commit` (kailos `ActionContext.after_commit`, que o
  `decide()` executa fora da transação; executores de ação aprovável NUNCA fazem isso inline).
- **Relatório/laudo sobre dado que é reescrito** (lake, tabela recarregada por pipeline) guarda um
  SNAPSHOT congelado das linhas de onde o número saiu, não só os ids: senão o relatório muda sozinho
  quando a base é reescrita.
- **Teste com concorrência real** usa fixture com dado commitado e conexão do pool por request
  (promoservice `tests/conftest.py` `race_env`: org e usuário apagados no teardown); o `client`
  padrão fixa UMA conexão com rollback e não enxerga corrida.

## 3. Conexão: rota de streaming e chamada externa lenta

- **Rota que devolve `StreamingResponse`/`sse_response` NUNCA recebe `Depends(get_conn)`**: o
  `yield`-dependency só fecha depois da resposta inteira, então um SSE de horas prende 1 conexão do
  pool (≈130 abas esgotam 8 workers × 16 e o resto do app espera `pool.timeout` sem erro no
  servidor). Use `Depends(get_conn_scope)` (`config/database.py`, devolve `ConnScope`) e abra
  `async with scope()` só nas fases de banco, ou um `pool.acquire()` curto; o gerador recebe só o
  pool/`db_scope`. Guarda: `tests/core/test_streaming_routes_no_get_conn.py` (dict `ALLOWED` só com
  motivo e dono da migração; exportação CSV finita é o caso aceito).
- **Mesma regra para rota/fetcher que chama HTTP externo lento** (Meta, Google, TikTok, gateway):
  `Depends(get_conn_scope)` + `async with scope()` só nas fases de DB; nunca `get_conn` atravessando a
  chamada ao provedor. kailos tem `as_conn_scope` (`config/database.py`) para função que aceita
  conexão OU scope.
- **Identidade e caminho de arquivo nunca vêm do corpo da requisição** (o chat de IA não lê path
  mandado pelo cliente; resolve anexo por id → `upload_access_service.resolve_authorized_upload`).
- **Postgres `LISTEN`** só por `listen_forever(CHANNEL, on_notify, dsn=DIRECT_DSN, on_resync=fn)`
  (`core/pg_listener.py`): reconecta com backoff, desliga `idle_session_timeout` na sessão (o
  Postgres de prod mata sessão que só escuta), usa o DSN direto (PgBouncer em transaction mode não
  suporta LISTEN) e chama `on_resync` a cada reconexão para recuperar os NOTIFYs perdidos. LISTEN
  cru num loop próprio parou a invalidação de permissão nos 6 apps (2026-11-13).

## 4. Índices exigidos pelo schema

- **Toda FK tem índice líder** (colunas da FK, em ordem, como início de algum índice/PK/UNIQUE);
  índice parcial só conta com predicado exatamente `col IS NOT NULL` (`WHERE deleted_at IS NULL`
  não serve a cascade). FKs de autoria (`*_by` → `users`) são isentas (usuário é soft-delete).
  `scripts/check_fk_indexes.py [--emit-sql]` + `tests/test_fk_indexes.py` (template) reprovam; só
  `ALLOWED_UNINDEXED` com motivo.
- **Coluna `url` das tabelas de upload** (`org_uploads`, `user_uploads`) tem índice (parcial em
  `deleted_at IS NULL`): o delete/lookup por URL varria a tabela.

## 5. Idempotência de POST (`Idempotency-Key`)

POST que envia mensagem ao cliente, move dinheiro/estoque ou cria recurso pago/duplicável é
idempotente no servidor, porque duplo clique, rede móvel que reenvia e 502 de proxy repetem a
requisição mesmo sem retry automático no front. Backend: `api/core/idempotency.py`
`run_idempotent(conn, organization_id, user_id, scope, key, work)` + tabela `idempotency_keys` +
`repositories/idempotency_repository.py` (kailos, akmeo, emporion, promoservice têm; **nexarena e
optimuslar ainda não** — copiar de kailos: helper, repositório e migration). `scope` = operação +
id do alvo (`whatsapp.send:42`). Mesma chave devolve a resposta guardada; em execução → 409; `work`
que levanta libera a chave. Sem header = comportamento antigo. Front: `lib/api/idempotency.ts`
`useIdempotencyKey` (reset no sucesso), header enviado pela config do service. Guarda desejada no
template: POST que chama `whatsapp_service.send_*` ou `settle_installment` passa por `run_idempotent`.

## 6. Datas

Cron e teste que usam `current_date`/`date.today()` contra janela de retenção longa levam `tz-ok:
<motivo>`. `AT TIME ZONE 'UTC'` dentro de `date_trunc`/`EXTRACT`/`to_char` sobre instante gravado é
reprovado pela guarda (é o dia UTC, não o da loja). Ver `local-time.md`.
