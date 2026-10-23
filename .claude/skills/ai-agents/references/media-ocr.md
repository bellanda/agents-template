# Mídia e OCR (imagem, vídeo, áudio, PDF)

> Reference do gate `ai-agents`. Canônico: `backend/src/api/core/agents/{media,ocr}.py` (docstrings de módulo
> são a spec), AGENTS_SUBSYSTEM.md §8. Upload/armazenamento de arquivo → skill `uploads-storage`;
> decode/resize de imagem → `image-processing`; PDF → `pdf-processing`.

## Matriz

| Entrada | Como | Modelo | Falhou |
| --- | --- | --- | --- |
| Áudio | `transcribe_audio` (POST JSON base64 em `{OPENROUTER_API_BASE}/audio/transcriptions`) | `Models.OpenRouter.WHISPER_LARGE_V3_TURBO` (`openai/whisper-large-v3-turbo`), pt | `None` |
| Imagem | `describe_media`/`describe_images` via LangChain | Claude Haiku 5.5 | `None` |
| Vídeo | 6 quadros amostrados com OpenCV, enviados como imagens (Haiku não aceita vídeo; o áudio do vídeo se perde) | Claude Haiku 5.5 | `None` |
| PDF com texto digital | MarkItDown (chat) ou `ocr` (texto nativo curto-circuita a rede) | — | — |
| PDF escaneado / foto de documento | `ocr.ocr_document` | Claude Haiku 5.5 (1 chamada/página) | `warnings` |

Haiku não aceita áudio nem vídeo inline e o PDF segue por MarkItDown/`ocr.py` (`supports_pdf_input/audio_input/video_input=False`; PDF inline do Haiku só após decisão testada). Trocar de modelo = flipar as
flags no `ModelConfig`; os ramos de `media.py` religam sozinhos.

## `media.py` — bytes → frase, sem conhecer canal

```python
text = await media_to_text(
    content, mime_type="audio/ogg", filename="audio.ogg",
    usage=UsageContext(thread_id=thread_id, agent_id=ENRICHMENT_AGENT_ID, tenant_id=org_id),
    message_id=str(message_id),
)                                   # str | None — o caller decide o que significa None
result = await describe_images([(jpeg1, "image/jpeg"), (jpeg2, "image/jpeg")],
                               prompt=LAUDO_PROMPT, context=listing_text, usage=ctx)  # VisionResult
```

Quatro decisões (onde apps que copiaram à mão erraram):
1. **Whisper ou nada** para áudio (sem degrau multimodal de queda com Haiku).
2. **Visão via LangChain** (`init_model` + `usage.runnable_config()`), nunca SDK cru → custo cai em
   `agent_message_usage` de graça; pelo SDK a mídia é invisível a qualquer teto.
3. **Custo do Whisper lançado à mão** (`record_transcription_cost`): a chamada não passa pelo callback e é
   cobrada por HORA de áudio (tokens 0). `cost_usd` = `usage.cost` devolvido pelo OpenRouter na resposta
   (`{text, usage:{seconds, cost}}`); `WHISPER_USD_PER_HOUR = 0.012` só como fallback.
4. **Retry diferenciado, fail-soft:** 429/5xx 2 tentativas com backoff; 401/400 não. Log SEMPRE com
   `status_code`. Nada levanta.
5. **O `format` do Whisper vem do MIME** (`media.whisper_audio_format`, dentro de `transcribe_audio`;
   substituiu `whisper_upload_filename`): o Whisper valida pelo formato/extensão, não pelos bytes. Áudio do
   WhatsApp chega como `audio/ogg; codecs=opus` sem nome; o caller passava `"arquivo"` ou a chave salva
   `wa-audio-….bin` e o Whisper respondia 400 → toda nota de voz caía no "não consegui ouvir" (kailos +
   nexarena prod, 2026-10-16). Caller passa o nome que tiver; o `media.py` deriva `ogg`/`mp3`/… do MIME.
6. **Transcrição vazia → 1 retry** (1 de 107 notas reais voltou vazia e ok na repetição).
7. **Provedor/endpoint (decisão do usuário 2026-10-22):** Whisper saiu do Groq-direto para o endpoint de
   speech-to-text do OpenRouter — uma chave só (`OPENROUTER_API_KEY`), 3,3x mais barato (US$ 0,012/h vs
   0,04/h; upstream DeepInfra, Groq só como fallback interno, ambos EUA → declaração de jurisdição à Meta
   segue verdadeira) e sem o 429 da conta Groq (82 de 107 áudios em rajada; OpenRouter: 107 áudios reais a
   concorrência 4 em 52 s, zero 429 — calibração kailos 2026-10-22). Qualidade equivalente (104 notas reais
   lado a lado). `provider.order` é ignorado neste endpoint. Corpo é JSON, NÃO multipart e NÃO compatível
   com o SDK OpenAI.
8. **Transcrição em lote (ex.: Insights) limita concorrência POR PROCESSO**, não por vendedor/item: os
   itens disparam em paralelo e um limite local por item multiplica.

### Ler a mídia de volta: SEMPRE pelo `StorageBackend`, nunca pelo disco

Mídia recebida do cliente é salva PRIVADA; em prod (`storage.backend: b2`) ela só existe no bucket
privado. Ler de volta para Whisper/visão = `storage.read_bytes(storage.key_from_url(url), public=False)`
(kailos `services/portals/whatsapp/inbound_media.py`). **PROIBIDO** `url_to_filesystem_path` +
`anyio.Path.exists()` fora de rota de serving local: no B2 o arquivo nunca está no disco, o `exists()`
dá `False` em silêncio e o agente responde o placeholder sem nenhum erro no log (kailos + emporion,
incidente 2026-10-16). Teste de regressão com um backend fake SEM disco (só `read_bytes` privado), nunca
com arquivo escrito em `get_upload_base()` — é exatamente o caminho que mascarou o bug.

**Foto salva em AVIF não vai crua ao modelo.** `save_upload` mode `image` transcodifica para AVIF, e o
Claude só lê JPEG/PNG/GIF/WebP inline: a data URL AVIF é recusada e o agente responde "não consigo ver"
mesmo com a leitura do storage certa (kailos 2026-10-16 14:11). Antes da visão, `image_bytes_for_model(
bytes, mime)` (mesmo `inbound_media.py`) devolve o original se o MIME já é aceito, senão re-encoda para
JPEG (`decode_image_bytes` + `cv2.imencode(".jpg")` em `anyio.to_thread`); imagem indecodificável → None
→ placeholder. Teste de regressão com AVIF de verdade (`encode_avif_bytes`) checando o magic `FF D8 FF`.
App que passa os bytes originais da Meta à visão (nexarena) não precisa.

- **Dica de domínio:** `extra_instructions: str | None` em `media_to_text`/`describe_media`/`describe_images`
  é ANEXADA ao prompt canônico (nunca substitui) — o app injeta vocabulário (placas, números de peito…)
  sem forkar o prompt; `core/agents/media.py` segue byte-idêntico ao template.
- Teto inline: imagem/doc 5 MB, vídeo 20 MB (base64 infla 33%). Armazenar é barato, mandar pro modelo não.
- `ENRICHMENT_AGENT_ID = "media-enrichment"` separa o custo de mídia do de conversa.
- Prompts em pt-BR (texto volta pro usuário brasileiro).

### Cache da leitura da mídia (`media_transcript`)

kailos `agent_dispatcher._row_to_text` / `_remember_transcript` (`whatsapp_message_repository.
set_media_transcript`): a primeira leitura de áudio (Whisper) ou imagem/vídeo (visão) é gravada na PRÓPRIA
linha da mensagem (`media_transcript`, já com prefixo `(áudio transcrito) …`); nos triggers seguintes
`_row_to_text` devolve o cache antes de reabrir o arquivo. Uma rajada do cliente dispara vários triggers
sobre as mesmas linhas, e sem o cache cada um pagava a mesma mídia de novo — mesmo com modelo que lê imagem
nativamente, o cache é o que impede repagar a cada turno. Best-effort: falha ao gravar só loga
(`media_transcript_persist_failed`), nunca derruba o atendimento. Ordem de resolução: metadata de
localização/contato → `text_body` → `media_transcript` → mídia (Whisper/visão) → placeholder.

### Ordem no canal que chama (WhatsApp/e-mail)

Grave o texto da mídia **ANTES** de disparar o agente. "Baixar mídia" e "responder" publicados juntos com
debounce fixo = corrida: o agente lê o placeholder, diz "não consigo ouvir áudio" e nada o chama de volta.
O trigger sai depois do enriquecimento, **inclusive quando ele falha** (silêncio é a pior degradação).

## `ocr.py` — PDF escaneado → Markdown

```python
doc = await ocr_document(raw_bytes, mime_type="application/pdf", usage=ctx,
                         extra_instructions=DOMAIN_HINT)   # opcional: anexa ao OCR_PROMPT, não substitui
doc.markdown, doc.page_count, doc.ocr_page_count, doc.warnings   # warnings: "page_3:degenerate_loop"
```

- Rasteriza com **pypdfium2** (`page.render(scale=200/72)` → numpy → JPEG q90 via OpenCV, lado máx 2400 px);
  deps: `pypdfium2` + `opencv-python-headless` + `numpy`. Sem pymupdf (stack PDF = pikepdf + pypdfium2).
- **Página digital pula a rede**: texto ≥ 200 chars E nenhuma imagem cobrindo ≥ 25% da página (envelopes
  assinados têm camada de texto em cima de scan — só `len(text)` devolve o timbre e perde o corpo).
- JPEG, não PNG (fan-out de 8 páginas = ~40 MB de base64 em PNG).
- Decodificação gulosa (`temperature=0`, reasoning OFF); falha típica é LOOP degenerado (n-grama de 5
  repetido >3×) → `_page_warnings` detecta e a página é refeita 1×.
- Concorrência 8 (`CapacityLimiter`), timeout 60 s/página e 180 s total, máx 20 páginas; uma página falhar
  nunca derruba o documento (`page_failed` em `warnings`). Foto de documento (`image/*`) = 1 página.
- `ValueError` só para entrada ilegível/não suportada/PDF com senha. Cada página = 1 chamada cobrada →
  sempre `usage`.
- Sem provedor de OCR dedicado (decisão 2026-09-30).

## Upload no chat playground

`POST /uploads` (`routes/uploads.py`): dono = `ctx["user_id"]`; gate de capability (415), tamanho, whitelist
MIME, quotas e dedup SHA-256; grava via `save_upload` (imagem→AVIF, documento por whitelist, nome
`{slug}-{uuid4}.{ext}`) + linha em `user_uploads`. Na mensagem: imagem → `image_url` inline; resto →
MarkItDown vira texto. App org-owned cria também `org_uploads` (skill `uploads-storage`).

## TTS — texto → fala (kailos, Modo TV, 2026-10-23)

- **Motor único `core/agents/speech.py`** (agents-template; módulo OPCIONAL, só app que fala — `sync_agents_to_another_fastapi_project.py --add-module speech`). API: `synthesize_speech(text, instructions, SpeechReference | None, timeout_seconds=)` → `SpeechResult(audio, generation_id, cost_usd)`, levanta `SpeechSynthesisError` (sem retry: quem espera tem teto e fallback); `record_speech_cost(result, usage=UsageContext)` grava a linha. Modelo = `Models.OpenRouter.FISH_AUDIO_DRAMA_3` no registry; trocar de voz = trocar o `SPEECH_MODEL`. O app fica só com o que é dele: o que falar, cache, arquivo e a POLÍTICA do teto. Canônico do uso: kailos `services/tv/voice_service.synthesize_clip` (único ponto que gera voz paga: alerta, preparo antecipado e prévia passam por ele).
- **Custo = preço por caractere, gravado NA HORA** (decisão 2026-10-23): a Fish cobra por caractere de `input` + `instructions` (+~6 dos colchetes; a transcrição da voz clonada NÃO é cobrada), US$ 2/1M (`input_price_per_1m=2.0`). Bateu 4 gerações reais de prod com 1–4% de erro. O `GET /api/v1/generation?id=<X-Generation-Id>` só indexa ~11 s DEPOIS do áudio (medido): consultar logo após deu 404 em 111 de 111 alertas (tudo virou estimativa fixa de US$ 0,0003), e esperar seguraria a trava do alerta/o preparo de 15 s. Preço mudou → atualize o registry (`GET /api/v1/models/<id>/endpoints`).
- **Teto de gasto antes de gerar:** toda geração paga consulta o teto do app (kailos `ai_budget.check`) no cache miss; estourado = sem geração (TV cai no speechSynthesis do navegador), mas frase em cache segue tocando (não custa). Sem isso a voz era a única IA paga que ignorava o teto.
- `POST {OPENROUTER_API_BASE}/audio/speech` com `{"model":"fish-audio/drama-3","input":<texto>,"response_format":"mp3","instructions":"Fale em português do Brasil, em tom <tom>."}`. Sem `voice`. Fish injeta `instructions` como direção entre colchetes no texto (e cobra esses caracteres).
- **Clonagem stateless:** `input_references: [{"type":"input_audio","input_audio":{"data":"data:audio/wav;base64,…"}}, {"type":"text","text":<transcrição>}]`. Referência que funcionou: clipes concatenados do maior para o menor, `ffmpeg -af highpass=f=80,afftdn=nf=-25,silenceremove=stop_periods=-1:stop_duration=0.6:stop_threshold=-40dB,loudnorm=I=-18 -t 60 -ar 24000 -ac 1` + transcrição via Whisper. Áudio casual de WhatsApp clona o timbre mas não a entonação de anúncio — peça 30–60 s gravados em silêncio no tom desejado.
- Só alguns endpoints clonam: confira `supports_voice_cloning` em `GET /api/v1/models/<id>/endpoints`. ElevenLabs no OpenRouter NÃO clona; HeyGen só devolve `pcm` e saiu bugado; Seed Audio leva ~30 s/frase; Gemini TTS não clona (vozes prontas, sai só PCM 24 kHz).
- ≈ US$ 0,0002–0,0003/frase, 2–4,5 s. **Cacheie por sha256(modelo, gravação, tom, texto)** e arredonde números variáveis em faixas (minutos 5/10/15/20/30/45/60) para o cache pegar.
- Se o áudio é parte do evento (ex.: alerta que não pode aparecer antes da voz), gere num consumer JetStream e publique o evento só depois; teto duro (~8 s) e fallback sem áudio. Canônico: kailos `services/tv/voice_service.py`, `docs/tv-mode.md`.
