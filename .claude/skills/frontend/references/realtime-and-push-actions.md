# Tempo real (SSE por usuário) + push com botões de ação

> Reference do gate `frontend`. Abra ANTES de ligar uma tela a eventos ao vivo (cards que se movem,
> contadores, faixas de pergunta) ou de criar notificação push com botões. Canônico: **kailos**.
> Inbox de WhatsApp (mesmo stream) → `whatsapp-inbox.md`. Decisão: CRM 2030, 2026-11-05.

## 1. UM stream SSE por usuário, montado na casca

- `hooks/useAppStream.ts` abre **uma** conexão por usuário/org; é montado em
  `routes/_authenticated.tsx` (`useAppStreamForCurrentOrg()`), estável entre rotas. Tela nenhuma abre
  `EventSource` própria; ela registra handlers.
- Registro: `lib/realtime/stream-registry.ts` (`registerStreamHandler(type, fn)`, `registerResync(fn)`).
  Handlers por domínio vivem em `lib/realtime/*-handlers.ts` e são importados uma vez no hook.
- **Reconexão** (`lib/realtime/reconnect.ts`): backoff exponencial 1 s..30 s com jitter em
  `[delay/2, delay]` (backend reiniciado não reconecta todas as abas no mesmo instante); o evento
  `online` do navegador pula a espera. Não pausa com a aba oculta (push/sino dependem do vivo).
- **Resync UMA vez por reconexão, só quando a nova conexão ABRIU** (sem replay, resync antes de abrir
  deixa um buraco). Resync = refetch só das queries ATIVAS.
- Token reativo (`useSyncExternalStore(subscribeAccessToken, ...)`): rotação de token reabre o stream.

## 2. Evento pequeno -> `setQueryData`, não invalidar lista

`lib/realtime/crm-handlers.ts` (`crm.attendance.updated`): o frame carrega só metadados
(`stage`, `temperature`, `version`, `changed[]`).

- `changed` ⊆ campos que o frame representa -> **patch in place** (`setQueryData`) no detalhe,
  `by-contact` e na linha da lista (paginada `{items}` ou infinita `{pages}`); a versão da linha da
  lista não sobe (lista nunca alimenta escrita; escrita usa a versão do detalhe).
- Qualquer outra coisa (cartão, dono, próximo passo) -> invalida SÓ aquele item.
- Evento não mais novo que a versão em cache é ignorado (`cached.version >= update.version`).
- Contadores de resumo: refetch coalescido (`SUMMARY_REFRESH_DELAY_MS`), não um por frame.
- Plug-in de tela com cache de formato próprio (o Quadro): `registerCrmPatchListener(fn)` roda a cada
  evento DEPOIS do patch padrão; retorna o unsubscribe (use em `useEffect`).
- Queries são achadas por **forma da key** (`findAll({predicate})`), pois o registry só tem o
  `QueryClient`.

Backend (`services/crm/realtime.py`, `services/realtime/frame_limiter.py`): efeito after-commit
(`infra` -> `due-queue.md`), dedupe por impressão do estado em janela curta (Valkey `SET NX PX`,
fail-open), destinatários = quem tem `crm:read_all` + o dono.

### Teto por conexão

`FrameLimiter` (puro, relógio injetado): <= 20 frames/s por conexão; mesmo `(type, id)` dentro de 1 s
vira UM frame final com o último payload (par `sent->delivered->read` nunca se perde, só se funde);
o excedente é descartado e substituído por UM `batch` (`{"type":"batch","payload":{"reason":"burst"}}`)
no próximo intervalo com folga. O cliente trata `batch` como "recarregar as colunas": refetch das queries
ativas, uma vez. Por quê: campanha de 2.000 contatos publicava milhares de eventos e travava o celular.

## 3. Push com botões de ação (sem abrir o app)

Fluxo (kailos `services/crm/question_push.py`, `question_tokens.py`, `question_token_answer.py`,
`routes/crm/question_token.py`; front `public/sw.js` + `public/sw-crm.js`):

1. Backend monta o push com `actions` (máx. 3; Android/desktop) e `data.tokens[option_id]`.
2. **Um token assinado, de uso único, por botão**: `base64url(payload).base64url(HMAC-SHA256)` com
   `payload = question_id|version|user_id|option|exp`. Chave derivada de `JWT_SECRET_KEY` com contexto
   fixo (`crm-question-token`): sem segredo novo, e um token nunca vira JWT nem o contrário. `exp` =
   expiração da pergunta; `version` prende o token à versão da linha, então qualquer mudança
   (respondida, substituída) o mata (trava de uso único = `expected_version` no UPDATE).
3. `sw.js` (branch genérico, antes do fluxo comum): `isQuestionPush(payload)` ->
   `applyQuestionOptions`; no `notificationclick`, `decideClick` devolve `answer` (botão com token) ou
   `open`. `answer` = `fetch` POST **sem credenciais** em `/api/v1/crm/questions/answer-by-token`;
   falhou (offline, vencido) -> `focusOrOpen(url)` como saída. A lógica pura mora em `sw-crm.js`
   (importado pelo SW e testado direto no vitest, sem `module.exports`).
4. Endpoint **sem sessão**, **sempre 204** (inválido, usado, vencido, opção errada, rate-limit: nenhum é
   oráculo para quem adivinha token). Rate limit por IP (30/min, Valkey, fail-open: o HMAC já barra
   forjar). Responde com o payload GUARDADO da opção, nunca com o que o cliente mandou; revalida que o
   destinatário ainda é membro ativo com a permissão.
5. **iOS não tem botões**: o corpo da notificação abre `/chat?crmq=<id>` (deep link); a faixa do topo
   destaca a pergunta. O `crmq` precisa **sobreviver ao redirect do login** (guard manda
   `redirect=<path+busca>` e valida que é caminho interno; `//evil` cai).
6. Push efêmero (sem linha em `notifications`): a faixa no app já é a pergunta. "Uma vez" = UPDATE
   condicional de `notified_at` ANTES de enviar. Orçamento de toques ao vendedor consultado antes.
7. Tamanho: payload com 3 tokens cabe em 4 KB (teste guarda).

## Testes que guardam

- Front: `lib/realtime/__tests__/crm-handlers.test.ts` (patch in place, invalida só o item, ignora
  versão velha, batch refaz só ativas), `hooks/__tests__/useAppStream.test.tsx` (1 conexão entre rotas,
  backoff+jitter, resync uma vez após abrir, batch = 1 refetch), `lib/push/__tests__/sw-crm.test.ts`,
  `routes/__tests__/crmq-login-redirect.test.ts`.
- Back: `tests/crm/test_realtime_events.py` (frame só para dono + `read_all`, coalescência),
  `tests/crm/test_questions.py` (token assinado/preso/expira, uso único sem oráculo, app vence a corrida,
  rate limit por IP silencioso, push 1x com tokens em 4 KB, membro removido não responde).
