> Reference do gate `integrations` (invariantes Meta — antes era a rule always-on `meta-integration.md`).
> Leitura curta, primeiro passo de qualquer trabalho Meta. Implementação completa → `meta-app-setup.md`.

# Meta Integration — Invariantes

Invariantes para qualquer projeto que integre com Meta (Facebook Login, WhatsApp Cloud, Instagram Graph). Implementação completa, Embedded Signup, Configuration setup, snippets HMAC → `meta-app-setup.md`.

## App Meta — 1 por SaaS

- **Cada SaaS = 1 Meta App próprio.** NUNCA compartilhe entre produtos. Hierarquia: 1 BM → N Meta Apps.
- **O mesmo App roda local/staging/prod.** Só URLs/domínios mudam por env.

## `.env` — 2 secrets, NUNCA duplicadas

```bash
META_APP_SECRET=                  # valida HMAC de X-Hub-Signature-256, signed_request, exchange ES
WHATSAPP_WEBHOOK_VERIFY_TOKEN=    # string aleatória que você escolhe; cola também na Meta
```

NUNCA crie `WHATSAPP_APP_SECRET` separado — é o mesmo `META_APP_SECRET` validando 3 surfaces distintas.

## `config/app/{env}.yaml` — público, versionado

```yaml
whatsapp:
  public_base_url: https://<projeto>.com.br # URL HTTPS que a Meta usa para webhooks
vite:
  meta_app_id: "<App ID>" # numérico do dashboard
  meta_es_config_id: "<Config ID>" # do Facebook Login for Business → Configuration
  meta_graph_api_version: v25.0
```

App ID, ES Config ID, Graph version são **PÚBLICOS** (aparecem no JS bundle). NUNCA em `.env`.

## Endpoints de webhook — naming canônico

| Webhook                        | Path                                  | Validação                                        |
| ------------------------------ | ------------------------------------- | ------------------------------------------------ |
| WhatsApp messages              | `/api/v1/webhooks/whatsapp`           | `X-Hub-Signature-256` HMAC com `META_APP_SECRET` |
| Deauthorize                    | `/api/v1/webhooks/meta/deauthorize`   | `signed_request` HMAC com `META_APP_SECRET`      |
| Data Deletion                  | `/api/v1/webhooks/meta/data-deletion` | `signed_request` HMAC com `META_APP_SECRET`      |
| Data Deletion status (pública) | `/data-deletion/{code}` (frontend)    | Sem auth; código aleatório é a "auth"            |

- Webhooks retornam `200` em <10s (Meta retry indefinido). Processamento pesado → NATS JetStream, e o 200 só sai DEPOIS do `publish` aceito: publish falhou → `503` (a Meta retenta; 200 aqui perde a mensagem). Ver "Pipeline do WhatsApp" abaixo.
- `signed_request` é **form field**, NÃO JSON body. Formato: `<base64url(sig)>.<base64url(json)>`.
- **OBRIGATÓRIO** gravar `facebook_user_id` em `portal_connections.metadata_extra` durante `connect_embedded_signup` — sem isso Deauth/Data Deletion validam HMAC mas não acham a conexão.
- **Tipo de mensagem inbound desconhecido NUNCA pode quebrar o persist.** A Meta cria tipos com o
  tempo. O toque em quick-reply de TEMPLATE chega como `type:"button"` (`button.text` + `button.payload`,
  `context.id` = wamid do template); o de mensagem interativa chega como `interactive.button_reply`.
  Outros exemplos: `order`, `system`, `request_welcome`. Gravar `msg["type"]` cru numa coluna com CHECK
  derruba a transação, o consumer esgota as redeliveries e a mensagem do cliente **some**: sem janela
  reaberta, sem SSE, sem IA/vendedor, e o botão de opt-out não registra nada (Kailos prod, 2026-10-15).
  Regra: o CHECK lista os tipos tratados (inclui `button`) e o persist rebaixa qualquer tipo fora da
  lista para `unsupported`, com o payload cru em `metadata`.

## Credencial do tenant — cifrada at rest

O token de acesso que volta do Embedded Signup é **permanente** e dá acesso à WABA do cliente. Ele
NUNCA fica legível no banco:

- Cifre na camada de **repositório**, antes de todo write — não no route, senão um caminho novo
  esquece.
- Coluna dedicada com nome que denuncia o conteúdo (`api_token_encrypted`), com prefixo de versão no
  valor (`v1:`) para permitir rotação de chave.
- Guardar dentro de um JSONB genérico (`token_data`) é o anti-padrão: some no meio de outros campos e
  vaza inteiro em qualquer dump, backup ou WAL.
- Em fila/mensageria **NUNCA** trafegue o token no payload — mande `phone_number_id` e re-resolva a
  credencial no consumer.

## `postMessage` do Embedded Signup — hostname ancorado no ponto

O widget devolve `phone_number_id`/`waba_id` por `postMessage`. A checagem de origem é pelo
**hostname parseado**, ancorado em `.facebook.com`:

```ts
const FB_ROOT_HOSTNAME = "facebook.com";
function isFacebookOrigin(origin: string): boolean {
  try {
    const { protocol, hostname } = new URL(origin);
    if (protocol !== "https:") return false;
    return hostname === FB_ROOT_HOSTNAME || hostname.endsWith(`.${FB_ROOT_HOSTNAME}`);
  } catch {
    return false;
  }
}
if (!isFacebookOrigin(event.origin)) return;
```

- `event.origin.endsWith("facebook.com")` cru casa `https://evil-facebook.com` e deixa uma página
  hostil completar o handshake (auditoria 2026-06).
- Lista fixa de subdomínios (`www`/`web`/`business`) é o erro oposto: o subdomínio varia por
  conta/locale e o FINISH era descartado em silêncio (Kailos prod, 2026-10-09).
- `event.data` vem como **string JSON** (exemplo oficial faz `JSON.parse`); aceitar só objeto
  descarta tudo.
- A ordem entre o postMessage e o callback do `FB.login` **não é garantida** (doc da Meta): o
  callback espera o desfecho por alguns segundos antes de decidir. Callback do `FB.login` NUNCA
  `async` — o SDK lança "Expression is of type asyncfunction"; chame um helper async por dentro.
- Erro do widget chega como `event: "ERROR"` ou `CANCEL` com `data.error_message`/`error_code` —
  mostre o texto da Meta, não "você fechou".

## Pipeline do WhatsApp — inbound, mídia, status (kailos canônico, 2026-10)

Arquivos em `kailos/backend/src/api/`. Cada item abaixo nasceu de incidente em prod; o PORQUÊ é o que
impede alguém de "simplificar" de volta.

**Webhook → 503 quando o enfileiramento falha** (`routes/portals/webhooks.py::whatsapp_webhook`)
- O `publish` no JetStream (`WHATSAPP_WEBHOOK_META_SUBJECT`) é `await`ado ANTES do 200. Falhou → `503`,
  e a Meta retenta com backoff próprio (~7 dias): é a fila durável de graça. Um `except` engolindo o
  erro e devolvendo 200 faz a mensagem do cliente sumir sem retry nem linha no banco.
- Fail-closed na assinatura: sem `META_APP_SECRET` → 503; sem header ou HMAC inválido → 403. JSON
  inválido/body não-objeto → 200 (retry não conserta payload ruim).

**Download de mídia recebida — retry por entrega** (`whatsapp_service.MEDIA_DOWNLOAD_ATTEMPTS = 5`,
`messaging/consumers/whatsapp_tasks_consumer.py`)
- O consumer passa `msg.metadata.num_delivered` ao handler; falha RELANÇA `MediaDownloadError` (NAK →
  reentrega) até a entrega nº `MEDIA_DOWNLOAD_ATTEMPTS`. Tem que ser igual ao `max_deliver` do stream
  `WHATSAPP_TASKS` (o consumer importa a constante).
- Quem dispara o agente de IA numa mensagem com mídia é o download (`trigger_agent=True`), DEPOIS do
  arquivo gravado: publicar o trigger junto do webhook era corrida contra o debounce de 5s e o agente
  lia o placeholder em vez da transcrição. Na ÚLTIMA entrega o trigger sai mesmo sem o arquivo
  (resposta sobre "uma imagem" > silêncio). Antes disso um `except` engolia tudo e o consumer dava
  ACK sempre: as "5 tentativas" nunca existiram.
- Mídia recebida é `visibility=tenant` (CNH, CRLV…), nunca pública → o front busca por blob autenticado.

**Mídia outbound por `media_id`** (commit `1f16722`, 2026-10-09; `prepare_outbound_media` /
`send_prepared_media` / dataclass `PreparedMedia`)
- Duas fases: `prepare_outbound_media` (SEM conexão de banco, roda em paralelo: valida/converte —
  webm→ogg/opus, JPEG/PNG —, `save_upload`, sobe os bytes em `POST /{phone_number_id}/media`) e
  `send_prepared_media` (UMA chamada barata à Meta + INSERT em `org_uploads` e `whatsapp_messages`, em
  sequência — conexão asyncpg não faz queries concorrentes). `media_id=None` = upload na Meta falhou →
  só então cai no `link` público.
- Várias fotos: preparar todas em paralelo e enviar em rajada na ordem é o que faz o WhatsApp do
  cliente agrupar em álbum (`services/agents/vehicle_photo_sender.py`).

**Marcar como lida (`mark_read`)** (`_handle_mark_read`)
- Best-effort e cosmético: o token NÃO vai no payload NATS (re-resolve por `phone_number_id`);
  qualquer erro vira `log.warning("mark_read_suppressed_error", …, exc_info=True)` e ACK — retry numa
  task cosmética só acumula fila. O motivo vai no log porque "o tique azul não aparece" não tem outro
  ponto de partida, e leitura marcada é capacidade declarada no App Review.

**Status (ticks) fora de ordem** (`02cc580` monotônico, `c9e4a16` stash; 2026-10-09)
- `update_status` só avança: rank `sent 1 < delivered 2 < read 3 < failed 4` no SQL do UPDATE
  (`_STATUS_RANK_SQL`); `failed` sempre vence. `apply_status` = update + `propagate_status_to_earlier`
  (lido/entregue vale para as mensagens anteriores do CONTATO, não só da conversa — cobre transferida).
- Status que chega ANTES da linha outbound (o INSERT só ocorre após a Graph devolver o wamid): `UPDATE`
  não acha linha → `cache.stash_unmatched_status` (Valkey `cache:whatsapp:wa_status:{wamid}`, TTL 120s,
  guarda o maior rank, fail-open) → `create_outbound` faz `pop_stashed_status` (GETDEL) e aplica o mesmo
  `apply_status`. A tabela `_STATUS_RANK` do cache e o SQL têm que ficar sincronizados.
- `statuses[].errors` vira `error = {errors, reason}` com `reason` em pt-BR
  (`meta_errors.describe_webhook_status_errors`); é o único lugar onde a loja descobre falha tardia
  (ex.: 131042 faturamento). Detalhe → `whatsapp-campaigns.md`.

**Resposta ao botão do template e opt-out** (`whatsapp_service.is_marketing_opt_out`,
`repositories/portals/whatsapp_message_repository.get_template_answered_by_button`,
`agent_dispatcher._active_message_block` / `_is_stale_button_reply`)
- `type:"button"` (ou `interactive.button_reply`) com texto/payload normalizado (maiúsculas, sem
  acento, sem pontuação nas pontas) igual a "PARAR PROMOCOES" = opt-out de marketing; texto livre só
  vale se for EXATAMENTE a palavra-chave (frase com "parar" é conversa). Opt-out grava, confirma em
  texto livre (a janela acabou de abrir) e NÃO aciona o agente. O texto do botão do template
  (`OPT_OUT_BUTTON_TEXT`) e o reconhecedor têm que andar juntos.
- `get_template_answered_by_button`: último inbound `button` → `replied_to_wa_id` → template outbound
  de MESMA conversa; devolve também `button_payload` (`tpl_interest:<template>:<carro|->`).
- O checkpoint do agente só guarda texto recebido, então `_active_message_block` injeta "MENSAGEM ATIVA
  ENVIADA PELA LOJA" no prompt (template + carro). Prefere o template RESPONDIDO; é descartado como
  `stale` (`_is_stale_button_reply`) se o toque está fora da janela de lookback ou se a loja mandou
  outro template depois dele (o cliente já reage ao mais novo). Sem respondido, usa o último template.

**SSE** (`routes/whatsapp/chat.py`, `routes/agents/chat.py`; commits `eed7f17`, `35c40d9`, `55c5f82`,
2026-10-09)
- Headers: `Cache-Control: no-cache, no-transform` (Cloudflare comprime/bufferiza sem o `no-transform`)
  + `X-Accel-Buffering: no`, e o nginx do app repassa com `proxy_pass_header X-Accel-Buffering;`
  (`config/nginx/snippets/api-proxy-pass.conf`) — em `INGRESS_MODE=gateway` o gateway central é outro
  nginx e sem o header segura o stream até cair (~125s). Timeout por location para o SSE (`55c5f82`).
  Lado cliente → skill `frontend`, `whatsapp-inbox.md`.

**Embedded Signup — conectar só com o `code`** (`7c67e74`, `3131023`, `b7c2341`; 2026-10-09)
- Em prod o `FB.login` devolvia o `code` mas o `postMessage` `WA_EMBEDDED_SIGNUP` nunca chegava. O
  front manda só o `code`; `POST …/embedded-signup` (`routes/portals/portals.py`) faz
  `exchange_es_code` → se faltar `waba_id`: `wa_client.discover_es_waba_id` (`/debug_token` com
  `app_id|app_secret` → `granular_scopes[whatsapp_business_management].target_ids`) → se faltar
  `phone_number_id`: `discover_es_phone_number_id` (`/{waba}/phone_numbers`). **Mais de uma WABA ou
  número = `RuntimeError` (400)**: o cliente refaz escolhendo um só — NUNCA adivinhar. Depois:
  `subscribe_app_to_waba`, `register_phone_number`, `verify_credentials`, `get_facebook_user_id`.
- `business_id` do FINISH é opcional. O postMessage vem como string JSON e de qualquer subdomínio
  `*.facebook.com` (seção acima); o front espera o desfecho por alguns segundos antes de cair no
  caminho "só code".
- O POST inteiro leva ~25s (`/register` ~24s, 2026-10-16). O front mostra progresso pela
  mutation (`connecting`) e liga `beforeunload` até a resposta chegar. Detalhe em
  `meta-app-setup.md` §7 "Estado pós-FINISH".

## Don'ts

- **NUNCA** responder 200 ao webhook do WhatsApp se o `publish` no NATS falhou — devolva 503 e a Meta retenta.
- **NUNCA** deixar status de entrega rebaixar a mensagem (lido → entregue) nem descartar status que chegou antes da linha (stash Valkey).
- **NUNCA** `WHATSAPP_APP_SECRET` separado — é `META_APP_SECRET`.
- **NUNCA** APP_ID/ES_CONFIG_ID/Graph version em `.env` — são públicos, vão em yaml.
- **NUNCA** log de `signed_request`/`X-Hub-Signature-256`/body bruto de webhook em prod.
- **NUNCA** valide HMAC com `==` direto — sempre `hmac.compare_digest` (timing-safe).
- **NUNCA** compartilhe 1 Meta App entre 2+ SaaS distintos.
- **NUNCA** guarde token de portal em claro (coluna ou JSONB) — cifre no repositório, antes do write.
- **NUNCA** valide `event.origin` por sufixo cru nem por lista fixa de subdomínios — hostname parseado ancorado em `.facebook.com`.
- **NUNCA** ponha token em payload de NATS/fila — mande `phone_number_id` e re-resolva no consumer.
- **NUNCA** marque Pages/Ad accounts/Catalogs/Pixels/Instagram como `required` na Configuration — trava clientes que não têm aquele asset.
- **NUNCA** envie mídia outbound por `link` público como caminho principal — suba os bytes em `POST /{phone_number_id}/media` e envie por `{"id": media_id}`; `link` só como fallback se o upload falhar. Os fetchers da Meta (Suécia/Dinamarca) são barrados por CDN atrás de geo-block/WAF da Cloudflare e a mídia fica presa em "sent" para sempre (Kailos prod, 2026-10-09).
