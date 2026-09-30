# Mídia e OCR (imagem, vídeo, áudio, PDF)

> Reference do gate `ai-agents`. Canônico: `backend/src/api/core/agents/{media,ocr}.py` (docstrings de módulo
> são a spec), AGENTS_SUBSYSTEM.md §8. Upload/armazenamento de arquivo → skill `uploads-storage`;
> decode/resize de imagem → `image-processing`; PDF → `pdf-processing`.

## Matriz

| Entrada | Como | Modelo | Falhou |
| --- | --- | --- | --- |
| Áudio | `transcribe_audio` (POST multipart Groq) | Whisper `whisper-large-v3-turbo`, pt | `None` |
| Imagem | `describe_media`/`describe_images` via LangChain | GLM 5.3 Flash | `None` |
| Vídeo | parte `video_url` inline (até 20 MB) | GLM 5.3 Flash | `None` |
| PDF com texto digital | MarkItDown (chat) ou `ocr` (texto nativo curto-circuita a rede) | — | — |
| PDF escaneado / foto de documento | `ocr.ocr_document` | GLM 5.3 Flash (1 chamada/página) | `warnings` |

GLM não aceita PDF nem áudio inline (`supports_pdf_input/audio_input=False`). Trocar de modelo = flipar as
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
1. **Whisper ou nada** para áudio (sem degrau multimodal de queda com GLM).
2. **Visão via LangChain** (`init_model` + `usage.runnable_config()`), nunca SDK cru → custo cai em
   `agent_message_usage` de graça; pelo SDK a mídia é invisível a qualquer teto.
3. **Custo do Whisper lançado à mão** (`record_transcription_cost`): multipart não passa pelo callback e é
   cobrado por HORA de áudio (tokens 0, `cost_usd` = duração × 0.04/h).
4. **Retry diferenciado, fail-soft:** 429/5xx 2 tentativas com backoff; 401/400 não. Log SEMPRE com
   `status_code`. Nada levanta.

- **Dica de domínio:** `extra_instructions: str | None` em `media_to_text`/`describe_media`/`describe_images`
  é ANEXADA ao prompt canônico (nunca substitui) — o app injeta vocabulário (placas, números de peito…)
  sem forkar o prompt; `core/agents/media.py` segue byte-idêntico ao template.
- Teto inline: imagem/doc 5 MB, vídeo 20 MB (base64 infla 33%). Armazenar é barato, mandar pro modelo não.
- `ENRICHMENT_AGENT_ID = "media-enrichment"` separa o custo de mídia do de conversa.
- Prompts em pt-BR (texto volta pro usuário brasileiro).

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
