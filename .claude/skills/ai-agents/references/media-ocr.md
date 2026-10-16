# Mídia e OCR (imagem, vídeo, áudio, PDF)

> Reference do gate `ai-agents`. Canônico: `backend/src/api/core/agents/{media,ocr}.py` (docstrings de módulo
> são a spec), AGENTS_SUBSYSTEM.md §8. Upload/armazenamento de arquivo → skill `uploads-storage`;
> decode/resize de imagem → `image-processing`; PDF → `pdf-processing`.

## Matriz

| Entrada | Como | Modelo | Falhou |
| --- | --- | --- | --- |
| Áudio | `transcribe_audio` (POST multipart Groq) | Whisper `whisper-large-v3-turbo`, pt | `None` |
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
3. **Custo do Whisper lançado à mão** (`record_transcription_cost`): multipart não passa pelo callback e é
   cobrado por HORA de áudio (tokens 0, `cost_usd` = duração × 0.04/h).
4. **Retry diferenciado, fail-soft:** 429/5xx 2 tentativas com backoff; 401/400 não. Log SEMPRE com
   `status_code`. Nada levanta.
5. **Nome do arquivo do Whisper vem do MIME** (`whisper_upload_filename`, dentro de
   `transcribe_audio`): a Groq valida pela EXTENSÃO do nome, não pelos bytes. Áudio do WhatsApp chega
   como `audio/ogg; codecs=opus` sem nome; o caller passava `"arquivo"` ou a chave salva `wa-audio-….bin`
   e a Groq respondia 400 → toda nota de voz caía no "não consegui ouvir" (kailos + nexarena prod,
   2026-10-16). Caller passa o nome que tiver; o `media.py` corrige.

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
