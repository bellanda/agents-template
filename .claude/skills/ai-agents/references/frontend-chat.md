# Frontend de IA (chat completo)

> Reference do gate `ai-agents`. Layout/largura/overlay/mobile → gate `frontend` PRIMEIRO. Canônico:
> `frontend/src/components/{ai-elements,chat,agent-config}/`, `frontend/src/lib/{api,thread-messages-cache}.ts`.
> Em projeto novo: copie os 3 diretórios + fetchers de `lib/api.ts` (sync não copia front — `propagation.md`).

## Peças

| Camada | Arquivos | Papel |
| --- | --- | --- |
| Primitivas | `ai-elements/` (`conversation`, `message`, `reasoning`, `tool`, `prompt-input`, `suggestion`, `attachments`, `context`, `confirmation`, `model-selector`…) | UI headless-ish do Vercel AI Elements; use, não reescreva |
| Chat | `chat/ChatView` (raiz), `ChatConversation`, `ChatMessage`, `ChatComposer`, `ChatModelPicker`, `ChatEmptyHero`, `ChatImageLightbox`, `ChatDragDropOverlay`, `ChatRejectionDialog` | composição |
| State | `chat/use-chat-session.ts`, `use-agent-selection`, `use-threads-query`, `use-attach-and-send` | sessão, picker, lista de threads |
| Cards | `chat/tool-results/` (`index.ts` registry, `types.ts`, `action-confirmation-result.tsx`) | `type → componente` |
| Config do agente | `agent-config/` | `tenant-config.md` |

## `useChatSession` (o hook que tudo usa)

`useChat` (`@ai-sdk/react`) + `DefaultChatTransport({ api: "/api/v1/agents/chat/completions" })`:

```ts
headers: () => (userId ? { "X-User-Id": userId } : {}),   // Bearer quando houver auth real; NUNCA user no body
body: () => ({ model: agentIdRef.current, agent_name, stream: true, session_id })
```

- **Throttle de render** do stream (`STREAM_THROTTLE_MS = 32`): `rawMessages` → estado com buffer; sem isso
  cada token re-renderiza a lista inteira.
- **Hidratação** por `sessionId`: cache (`thread-messages-cache`) → senão `fetchThreadMessages` → `toUIMessages`.
  `onFinish` invalida o cache da thread e `threadsQueryKey` (TanStack Query). Estado server = Query; não
  duplique em Zustand (`frontend` ref state).
- **Anexo SEM texto é mensagem válida** (system prompt + documento bastam): nunca exija texto nem desabilite
  o enviar por isso. `handleSubmit` sobe os arquivos (`uploadFile`) ANTES do `sendMessage` e troca
  `data:`/`blob:` por URL persistida; `UploadError` tipado vai pro toast/dialog de rejeição.
- `singleShot` limpa a conversa a cada envio (agente one-shot).

## Tool result como card

Backend devolve `{"type": "<discriminator>", "data": {...}}` (`tool_envelope.py`); front:

```ts
const REGISTRY: Record<string, ComponentType<{ data: never }>> = {
  action_confirmation: ActionConfirmationResult,
  my_domain_card: MyDomainCard,          // entrada do APP, ao lado da tool que emite
};
```

`resolveToolResult(output)` faz parse (objeto OU string JSON) e devolve `{Renderer, data}`; sem entrada →
bloco `Tool` colapsado com o JSON cru. Discriminador = chave do registry EXATA. **Nunca** `if (type === …)`
dentro de `ChatMessage`. Chaves ficam snake_case (sem conversão camelCase). Tipo novo: Pydantic/dict no
backend + card + entrada no registry + tipo em `types.ts`.

## Reasoning, tools e mensagem

`ChatMessage` mapeia `parts`: `text` → `MessageResponse` (Streamdown, nunca parser Markdown caseiro);
`reasoning` → `Reasoning/ReasoningTrigger/ReasoningContent` (colapsado, auto-abre durante o stream);
`tool-*` → estados `input-streaming | input-available | output-available | output-error…` em `Tool*` ou card
do registry; `file` → chip/lightbox. `memo` no item — lista longa + stream exige isso.

## Anexos

`ChatComposer.buildAcceptAttribute(capabilities)`: documentos sempre (viram texto via MarkItDown);
`image/*`, `audio/*`, `video/*` só se o agente declara `capabilities.image_input|audio_input|video_input`
(vem de `GET /agents`). Validação client-side é conveniência; o gate real é 415/400 no backend.
Drag-and-drop com `ChatDragDropOverlay`; limites/quotas → `frontend/references/file-upload.md` e
`uploads-storage`.

## Custo e contexto

O backend grava `usage` (tokens + `cost_usd`) na mensagem assistant do `chat_history` e em
`agent_message_usage`. Para exibir, use a primitiva `ai-elements/context.tsx` (`Context*`: tokens usados /
janela / custo) alimentada por esse `usage` — o template traz a primitiva, mas `ChatMessage` ainda não a
renderiza; ligue onde o produto quiser mostrar (rodapé da mensagem ou barra do composer). Custo agregado por
thread/usuário/tenant: `usage-cost.md`. Nunca calcule preço no front — use o que o backend devolve.

## Sugestões

`AgentSuggestionInstant` (`label`, `prompt`, `section`, `action: fill|attach`, `emoji`) e
`AgentSuggestionTemplate` (placeholders). `fill` só escreve no composer; `attach` escreve, abre o picker e
envia sozinho quando há arquivo (fluxos "analise este contrato"). Ausente/desconhecido = `fill`.

## Erros e UX

`onError` → toast do `err.message`; `ChatRejectionDialog` para upload rejeitado (capability/tamanho/quota);
botão parar = `stop()`; estado `isHydrating`/`isUploading` desabilita enviar. Sem `console.log`.
