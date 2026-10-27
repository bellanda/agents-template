# Ligações de voz do WhatsApp (Meta Calling API) — atender no app via WebRTC

> Padrão da frota (2026-10-27). v1 nasceu no **emporion** (ab1faff, 2026-10-25/26: permissão
> `call:answer` + flag por aparelho, só SSE). A versão completa abaixo é do **kailos** (piloto
> 2026-10-27, número da Promocar), que vira o canônico: lista de quem atende, push tocando,
> "Fulano atendeu", seção "Ligações". emporion e nexarena recebem essa versão na rodada de
> padronização. App sem WhatsApp Cloud API (akmeo, promoservice, optimuslar, template): não se aplica.

## Decisões (não re-litigar)

- **Só API oficial (Cloud API), sem SIP, sem coexistência.** A Meta não suporta Calling em número
  de Coexistence (tabela de features do Embedded Signup "Not supported (Cloud API)"). Com SIP ligado
  as ações via Graph param de funcionar (131055).
- **O navegador é o telefone.** O backend só sinaliza (webhook + Graph); o áudio é WebRTC direto
  entre o navegador de quem atende e a mídia da Meta (ice-lite, IP público → STUN basta; sem TURN
  até aparecer rede corporativa que precise).
- **Só ligações recebidas (USER_INITIATED).** Ligar para o cliente (business-initiated) exige pedido
  de permissão (`call_permission_request`, 1/24h e 2/7d por par, permissão temporária de 7 dias),
  é cobrado em pulsos de 6 s pela tabela BRL e ficou para depois. Recebidas são grátis.
- **Quem atende = lista explícita por org** (`whatsapp_call_answerers`), não permissão. Ligar/
  desligar e editar a lista = permissão de gerenciar o portal (`portal:manage`; ler = `portal:read`).
  Superusuário NÃO fura a lista: quem não está nela não toca nem atende.
- **Toca em todos ao mesmo tempo; o primeiro a atender leva** (claim atômico). Os outros veem
  "**Fulano atendeu e está falando**".
- **Recusar com várias pessoas** = "não posso" só para mim (set no Valkey). Quando TODOS recusam, o
  backend faz o `reject` na Meta. Com uma pessoa só, recusar desliga na hora.

## Requisitos da Meta (a seção mostra cada um com ✓/✗ ao vivo)

1. Número na **Cloud API** (não no app WhatsApp Business do celular).
2. **Teto de mensagens ≥ 2.000/dia.** Desde **2025-10-08** o teto é do **portfólio**
   (`whatsapp_business_manager_messaging_limit`, lido no número, na WABA ou no business). O campo
   antigo `messaging_limit_tier` NÃO volta mais no número (verificado em prod 2026-10-27) — código
   que lê só ele cai no default. Abaixo de 2K a ativação falha com **138015**. Número de teste da
   Meta é isento.
3. **Campo `calls` assinado no webhook do app Meta** (App Dashboard → WhatsApp → Configuração →
   Campos do webhook). É por APP (1 Meta App por SaaS = marcar em cada app). Conferir por
   `GET /{app-id}/subscriptions` com app token `{app_id}|{app_secret}` (nunca logar). Sem isso nada
   chega — a primeira coisa a checar quando "não toca".
4. `whatsapp_business_messaging` no número (já vem do Embedded Signup); método de pagamento válido
   na WABA (131044).
5. Microfone liberado: nginx `Permissions-Policy: microphone=(self)` (o site público da loja fica
   `microphone=()`).

## Ajustes do número (`POST /{phone_number_id}/settings` → objeto `calling`)

- `status`: `ENABLED`/`DISABLED` (GET devolve `NOT_SET` antes da primeira vez).
- `call_icon_visibility`: **sempre `DEFAULT`** (ícone de ligar visível, qualquer cliente liga),
  enviado junto com o `status` em todo toggle. **Sem "modo teste"** (decisão do usuário
  2026-10-27, depois do piloto: "não precisa daquele só X pode ligar"): a seção é só liga/desliga.
  `DISABLE_ALL` (só liga quem recebe o botão de ligação) existe na Meta mas não é exposto; mandar
  `DEFAULT` a cada toggle também desfaz um `DISABLE_ALL` que tenha ficado no número. Na prática o
  `DISABLE_ALL` nem segurou o piloto: o testador ligou direto pelo ícone (a Meta leva dias para
  propagar a visibilidade).
- A Meta avisa que mudança de visibilidade pode levar **até 7 dias** para aparecer; feedback
  negativo pode pausar o recurso por 7 dias; baixa taxa de atendimento pode esconder o botão
  (`restrictions` no GET).
- Ainda não usados: `call_hours` (fuso + até 2 faixas/dia + feriados; update substitui tudo),
  `callback_permission_status`, `voicemail`, `audio.additional_codecs`, `sip`.
- Toda leitura de enum da Meta passa por mapeamento com fallback `UNKNOWN` (invariante de enum
  externo).

## Botão de ligação (mensagem)

Interactive `type: "voice_call"`, `action: {name: "voice_call", parameters: {display_text ≤20,
ttl_minutes 1–43200 (default 10080)}}`, corpo de texto. Mensagem livre = precisa da janela de 24 h;
fora dela, template com botão `voice_call`. No inbox entra pelo menu de anexos ("Botão de
ligação"), salvo como `message_type="interactive"` + `metadata.send_kind="call_button"` (o valor
`interactive` já está no CHECK). O `cta_payload` volta no `connect` se mandarmos `payload`.

## Fluxo

1. Webhook `calls` `event=connect` (`direction=USER_INITIATED`, `session.sdp_type=offer`) entra pelo
   MESMO endpoint e consumer JetStream das mensagens; `handle_inbound_webhook` desvia
   `field == "calls"` antes do bloco de mensagens (`calls/webhook.py`).
2. Upsert idempotente em `whatsapp_calls` por `wa_call_id`; contato/conversa criados se preciso SEM
   disparar turno de IA; **SDP só no Valkey** (`cache:whatsapp:call_offer:{call_id}`, TTL 90 s;
   nunca no banco, nunca no log, nunca no SSE). Evento `call.incoming` para a lista.
3. Mesmo `connect` publica `whatsapp.call.ring` → consumer do **toque** (trabalho longo por chave:
   semáforo + `msg.in_progress()`): push efêmero a cada ~4 s enquanto `ringing`, teto 60 s.
4. Atender: `GET /offer` → `RTCPeerConnection` (`setRemoteDescription`, `getUserMedia`,
   `createAnswer`, espera o ICE completo — não-trickle — ~3 s) → `POST /answer {sdp}`. Backend
   reivindica (`ringing→answering`; perdeu = 409), chama `pre_accept` e `accept` com o **MESMO** SDP
   (a Meta recusa SDP diferente), vai a `in_progress`. Erro da Graph = `failed` + 502 pt-BR. Mídia só
   depois do 200 do `accept`.
5. `terminate` (só quem atendeu; sempre chamar ao desligar do nosso lado). Webhook `terminate` é a
   verdade do desfecho: `COMPLETED` com duração = `completed`, sem duração = `missed`, `FAILED` =
   `failed`, resto = `unknown`; recusa nossa preservada como `rejected`.
6. A Meta desiste em ~30–60 s sem resposta (cliente vê "Não atendida"). Sem mídia por 20 s no início
   ou 30 s no meio, a ligação cai.

## Dados, rotas e eventos (kailos canônico)

- `whatsapp_calls` (status: `ringing, answering, in_progress, completed, missed, rejected, failed,
  unknown`; direction: `user_initiated, business_initiated, unknown`; `answered_by_user_id`,
  `duration_seconds`, `metadata` = payload cru SEM SDP). `whatsapp_call_answerers(organization_id,
  user_id)` PK composta; efetivos = JOIN com os membros ativos da org.
- Rotas `/organizations/{org_id}/whatsapp/calls`: `GET /stream` (SSE só `call.*`), `GET /active`
  (a ligação tocando para mim — usado ao abrir pelo push e ao reconectar, SSE não tem replay),
  `GET /{id}/offer`, `POST /{id}/answer|decline|terminate`, `GET /by-contact/{contact_id}`
  (marcadores da conversa), `GET|POST /settings`, `GET|PUT /answerers`.
- SSE por usuário (NATS): `call.incoming`, `call.answered` (com `answered_by_name`),
  `call.declined` (só para os aparelhos de quem recusou), `call.ended`.
- Notificação com linha no sino só para **perdida** (`whatsapp_call_missed`, CHECK de
  `notifications` E de `notification_preferences`), com `group = call:<id>` para substituir a
  notificação que estava tocando.

## Push "tocando" (o máximo que a web entrega)

- Payload efêmero (sem linha no sino): `type: whatsapp_call_incoming`, `group: call:<id>`,
  `TTL` ~30 s, `Urgency: high`, url `/chat?contact=<cid>&call=<id>`.
- `sw.js`: cada push = notificação **NOVA** (tag `call:<id>:<Date.now()>`) depois de fechar as do
  mesmo group (`closeGroup`); `requireInteraction`, `vibrate`, ações "Atender"/"Recusar" (viram
  `&intent=answer|decline` na URL — o SW não tem token para chamar a API). Aba visível = não mostra
  (o diálogo já está na tela).
- **Android/desktop (FCM):** re-push a cada **~4 s** (abaixo dos ~5 s que o Android deixa o banner
  heads-up na tela). Só notificação NOVA faz o banner descer de novo + vibrar + tocar; a 1ª versão
  (tag FIXA + `renotify`) só atualizava a da bandeja e o banner recolhia — o usuário pediu "estilo
  Whats, fica animando aparecendo a notificação" (2026-10-27). Tela cheia de ligação (full-screen
  intent / CallKit) NÃO existe na web — é o limite.
- **iOS (endpoint `*.push.apple.com`):** só o PRIMEIRO push (iOS ignora vibração/requireInteraction,
  não tem ações e empilharia banners). Web app NÃO tem CallKit nem toque contínuo com o celular
  bloqueado — não prometa. Para atender, o app precisa estar aberto (o toque na notificação abre).
- Ao resolver: push `whatsapp_call_settled` silencioso no mesmo group ("Fulano atendeu"/"Encerrada"),
  que fecha a que tocava (`closeGroup`) — no Chrome todo push precisa mostrar algo.
- Abrir pelo push: o provider global lê `?call=`, consulta `GET /active` e abre o diálogo; limpa os
  params com `replace`.

## Frontend

- `CallProvider` montado no shell autenticado (stream PRÓPRIO; o stream do chat só existe na tela de
  chat). `useCallSession` = máquina `idle → ringing → connecting → active → ended`, mais
  `answered_elsewhere` ("Fulano atendeu e está falando", cronômetro, fecha em ~5 s).
- `IncomingCallDialog`: Dialog (tela cheia no celular), anel pulsando no avatar
  (`prefers-reduced-motion` desliga), Atender/Recusar grandes, mudo, cronômetro, desligar; toque via
  Web Audio (sem arquivo); autoplay bloqueado → "Toque na tela para ativar o som".
- Seção **"Ligações"** (`?settings=calls`) em "Primeiros passos", **entre "Templates do WhatsApp" e
  "WhatsApp Business"**: requisitos ✓/✗, "Receber ligações" (só liga/desliga), "Quem atende" (multi-seleção de membros, padrão `QueueMembersPanel`), "Neste aparelho"
  (tocar aqui — localStorage `<app>:…`; push; testar microfone; testar toque).
- Inbox: marcador da ligação na linha do tempo, selo "Em ligação · Fulano · 01:23" no cabeçalho da
  conversa, "Botão de ligação" no menu de anexos.

## Limitações conhecidas

- iOS em segundo plano: só o primeiro aviso; sem toque contínuo.
- Navegador sem gesto prévio bloqueia áudio de toque; vibração também exige ativação.
- Só STUN público; NAT simétrico/firewall rígido pode falhar (`iceConnectionState=failed` → encerra
  e chama `terminate`).
- BSUID (2026): o `from` pode deixar de ser telefone — não assuma número.

## Fora de escopo (proposto, não feito)

`call_hours` a partir do horário da loja; ligar para o cliente; mensagem automática da IA depois de
uma perdida; TURN; gravação/transcrição da ligação.
