# Atendimento WhatsApp — inbox (`/chat`) com SSE

> Reference do gate `frontend`. Abra ANTES de construir/alterar a caixa de entrada de conversas de um
> canal de mensagens (WhatsApp) em qualquer app: lista de conversas + janela de chat + envio +
> tempo real. Backend (webhook, janela de 24h, política Meta, handoff, filas) → gate `integrations`.
> Decisão de **2026-10-01**: o inbox do **kailos** é o canônico. balizap alinha a ele (e corrige o
> SSE, abaixo); nexarena `/atendimento` adota o mesmo inbox **sem** filas/transferência.

## Canônico (onde copiar)

| Peça                                | Fonte (kailos `frontend/src/`)                                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Rota                                | `routes/_authenticated/chat/index.tsx` (sem `$id`: a org vem do seletor global; `scope`/`userId` na URL via `validateSearch`)                    |
| UI                                  | `components/whatsapp/*` — `ChatSidebar`, `ChatSearchInput`, `ChatWindow`, `ChatWindowHeader`, `ChatWindowFooter`(+`WindowBanner`), `ChatTimeline`, `MessageBubble`, `EventCard`, `DaySeparator`, `Composer`, `MobileTabBar` |
| Dados + tempo real                  | `hooks/useWhatsAppChat.ts` (conversas infinitas, mensagens, envio otimista, retry, transferir, fechar, desbloquear, `useWhatsAppStream`)         |
| Transporte SSE                      | `lib/api/services/whatsapp-stream.ts` (`openWhatsAppStream`) · REST/tipos em `lib/api/services/whatsapp.ts`                                      |
| Bolhas otimistas                    | `stores/whatsapp-optimistic-store.ts` (por `contactId`, `useSyncExternalStore`)                                                                  |
| Tema                                | `index.css` → `.whatsapp-theme` + `.dark .whatsapp-theme` (vars `--wa-*`)                                                                         |

## Anatomia e layout

- **Layout `SidebarChatLayout`** (full-bleed, sidebar/header intactos). Raiz da página:
  `whatsapp-theme flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-[var(--wa-panel)]` — altura
  por `flex-1 min-h-0`, nunca `h-[calc(100dvh-…)]`.
- **Desktop (≥md):** lista `md:w-[360px] lg:w-[400px]` + janela `flex-1`, lado a lado.
- **Mobile (<md):** UMA das duas visões por vez (`mobileView: "list" | "chat"`), trocada por CSS
  (`hidden md:flex` nos dois painéis — nunca `useIsMobile()`); selecionar conversa → `"chat"`, botão
  voltar do header → `"list"`. `MobileTabBar` (Conversas | Chat, badge de não-lidas, `safe-area`
  inferior) fecha a tela; "Chat" fica `disabled` sem conversa selecionada.
- **Estado de seleção:** `selectedContactId` em `useState` (efêmero); `scope` (`mine|all`) e
  `userId` (filtro de atendente, só com `read_all`) na **URL**; busca com debounce (250ms) em
  state local. Selecionar zera o badge de não-lidas otimista
  (`useMarkConversationReadOptimistic`, espelha o side-effect do `GET …/messages` no backend).
- **Lista:** scroll infinito de 20 (`useInfiniteQuery` + `useInfiniteScrollSentinel` + "Carregar mais"; sem `IntersectionObserver`, ver `list-screen.md`), estado da
  conversa em badge (IA · atendente · Finalizada), prévia por tipo de mídia, hora relativa.
- **Janela:** header (estado, atribuição, menu de transferência quando `canManage`), `WindowBanner`
  (aviso a ≤3h do fim da janela de 24h, vermelho quando expirou — envio livre bloqueado, só
  template), timeline (`DaySeparator`, `EventCard` = divisor de transição de estado entre as bolhas,
  não item de auditoria), `Composer` (texto, anexo com prévia, áudio por `MediaRecorder`; **anexo sem
  texto é mensagem válida**, ver `file-upload.md`).
- **Papéis de leitura** (`accessRole`: `read_all | assigned | historic`): `read_all`/`historic` leem e
  **não escrevem**; cada botão pergunta pela permissão que o backend cobra (`whatsapp:read_all`,
  `whatsapp:manage`), não por "é gestor".
- **Sem filas/transferência (nexarena):** não monte `useTransferConversationToQueue`/menu de equipe;
  o resto (lista, janela, composer, SSE) é idêntico.

## Tempo real — SSE keyed por ORG, não por contato ativo

```ts
useWhatsAppStream(orgId); // deps do effect: [accessToken, auth, queryClient, orgId] — NUNCA o contato aberto
```

**O bug do balizap (corrigir ao alinhar):** `useWhatsAppStream(activeContactId)` colocava o contato
aberto nas deps do `useEffect`. Cada clique na lista **derrubava e reabria o SSE**, e como não há
replay, os eventos da janela de reconexão se perdiam (mensagem nova que só aparece no próximo refetch). O
handler **não precisa** saber a conversa ativa: ele invalida `["whatsapp","conversations"]` e
`["whatsapp","messages", payload.contactId]` com o `contactId` do próprio evento, o que já cobre a
conversa aberta.

Invariantes do stream (todas já no canônico — não remova ao adaptar):

- **Resposta SSE do backend com `Cache-Control: no-cache, no-transform` + `X-Accel-Buffering: no`**
  (vale para TODO `text/event-stream`: inbox, chat de agente, quadro de pedidos). Sem o
  `no-transform` a **Cloudflare** comprime e bufferiza o stream: o nginx entrega os heartbeats, o
  browser não recebe nada, a conexão cai em ~125s e a tela "só atualiza com F5" (Kailos prod,
  2026-10-09). Diagnóstico: `body_bytes_sent` crescendo no log do nginx + nenhum evento no browser.
- **Ressincroniza ao reconectar:** não há replay, então a cada reabertura (menos a primeira) o loop
  invalida `["whatsapp","conversations"]` e `["whatsapp","messages"]` — o que aconteceu com o
  stream fora do ar só aparece via REST (`onReconnect` do `useReconnectingStream` no balizap; loop
  inline no kailos).

- **Um stream por org**, aberto com `?org_id=` explícito. Sem isso o backend adivinha o primeiro
  vínculo e quem tem duas lojas via a caixa de uma com eventos da outra.
- **O evento é SINAL, não conteúdo** (`WhatsAppMessageSignal { contactId, conversationId }`): o
  stream diz "mudou algo na conversa X" e o REST (gateado por permissão) entrega o dado. Nunca
  carregar o texto no evento.
- **`fetch` + `ReadableStream` com `Authorization`** (EventSource não manda header); frames
  `data:` separados por `\n\n`, heartbeat `:` ignorado, chaves normalizadas p/ camelCase.
- **Token reativo:** `useSyncExternalStore(subscribeAccessToken, getAccessToken)` nas deps — rotação
  de token (local ou de outra aba) reabre o stream com o token novo; cobre o cold-load em que o
  token só chega depois do mount.
- **Reconexão:** loop `while (!closed)` com espera de 2s; falha **401/403** → `auth.refreshToken()`
  (single-flight, mesmo lock do `ApiClient`) e reconecta; refresh que também dá 401/403 = sessão
  morta → para (a dep reativa reabre quando houver login). O `status` viaja no erro justamente
  para o chamador distinguir "token expirou" de "backend caiu".
- **Cleanup:** `AbortController.abort()` + `closed = true` no return do effect.

## Envio otimista

`useWhatsAppSend`: `onMutate` cria bolha `tmp_<uuid>` (`status: "pending"`) no store otimista
(a key do cache usa o MESMO `orgId` da query, senão a bolha nasce sem conversa); `onError` marca
`failed` (a bolha fica para **retry** via `useRetryFailedMessage`); `onSuccess` remove a tmp e
invalida mensagens + conversas. `useWhatsAppMessages` mescla servidor + tmp (mesma direção, mesmo
texto, `createdAt` ≤ 60s) para a invalidação do SSE não apagar a bolha antes da resposta.

## Tema — vars `--wa-*` (exceção deliberada a "sem cor crua")

O inbox imita a identidade do canal. As cores vivem **escopadas** em `.whatsapp-theme` (+ variante
`.dark`), com hex dentro da classe e `bg-[var(--wa-…)]` nos componentes: `--wa-brand`, `--wa-teal`,
`--wa-outbound-bg/fg`, `--wa-inbound-bg/fg/border`, `--wa-read-tick`, `--wa-panel` (fundo),
`--wa-panel-header/hover/active`, `--wa-day-chip-bg/fg`, `--wa-meta-fg`, `--wa-unread-bg/fg`.
Fora do escopo `.whatsapp-theme` vale a regra normal (vars semânticas shadcn). **NUNCA** hex cru
dentro de componente do inbox — sempre `var(--wa-*)`.

## Anti-padrões

- **NUNCA** `activeContactId`/contato selecionado nas deps do stream (reconecta a cada clique).
- **NUNCA** polling (`refetchInterval`) no lugar do SSE (nexarena hoje faz 10s — migra; backend
  ganha o stream).
- **NUNCA** `EventSource` (sem `Authorization`) nem stream sem `org_id`.
- **NUNCA** `text/event-stream` sem `no-transform` no `Cache-Control` (Cloudflare bufferiza).
- **NUNCA** conteúdo de mensagem no evento SSE; **NUNCA** `useIsMobile()` para trocar lista/chat.
- **NUNCA** `h-[calc(100dvh-Xrem)]` no chat; **NUNCA** botão de enviar desabilitado com anexo e sem texto.
- **NUNCA** inbox próprio por app — copie o do kailos; diferença legítima é só a presença de equipes.
