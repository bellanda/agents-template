---
paths:
  - "backend/**"
  - "**/*upload*"
  - "**/*storage*"
---

# Uploads & Storage — Invariantes

> **MANDATÓRIO — invocar skill `uploads-storage` ANTES de codar.** Qualquer upload (arquivo/imagem/doc/mídia/áudio/vídeo/export) em qualquer linguagem (Python/Rust/Go) e qualquer storage (local NVMe / B2 / S3 / Azure / GCS). Esta rule é só invariantes + don'ts; API completa (`save_upload`, modes, filename regex, layout, Pydantic, repository, `StorageBackend` Protocol) na skill.

## Invariantes universais

1. **Wrapper único** `save_upload(file, *path_parts, mode, ...)` — boundary única de IO. Nunca grave bytes direto, nunca monte URL na mão.
2. **Duas tabelas, tenancy NOT NULL**: `org_uploads(organization_id)` e `user_uploads(owner_user_id)`. Zero arquivo anônimo. Projeto cria só a(s) que usa.
3. **Filename**: `{slug}-{uuid4}.{ext}` — slug NFKD ASCII ≤60, uuid4 hyphenated full-length, ext lowercase via `ext_from_name(name, mime)`.
4. **Modes**: `raw` (bytes as-is) | `image` (→ AVIF, resize por profile, sem upscale) | `document` (MIME whitelist + ext preservada).
5. **Visibility** + `metadata.acl`: `public` (UUID4 122 bits é a auth, ~95% dos casos) | `tenant` (org/user check) | `private` (owner only). Em **object storage** o eixo de visibility mapeia em **buckets** (acesso B2/S3 é bucket-wide, sem flag por objeto): `public` → bucket público (URL estável/CDN, anônima) · `tenant`/`private` → bucket privado (presigned, atrás do gate). ⇒ **2 buckets por env**.
6. **`StorageBackend` Protocol**: `save_bytes` / `delete_file` / `delete_tree` / `build_url` / `presigned_url` / `key_from_url` + flag `is_remote`. Troca local ↔ object storage sem tocar business. Seleção via `settings.storage.backend`. **Hint `public: bool`** em `save_bytes`/`delete_file`/`build_url` roteia o bucket (público vs privado) no backend remoto; o local ignora. `delete_tree` NÃO tem hint (um subtree pode misturar visibilities → limpa ambos os buckets). Serving ramifica em `is_remote`: local → `FileResponse`; remoto → **link privado estável + 302 redirect cacheável** (`get_private_link`: um presign por arquivo por dia no Valkey, B2 devolve `Cache-Control: private, immutable`; presign novo a cada request multiplica o egress do B2 — kailos 2026-10-23, skill §8 item 6).
7. **Referência**: FK single-instance (logo/banner/avatar) OU join table multi-instance (photos/gallery/docs) → `org_uploads(id)`/`user_uploads(id)`. URL inline solta = PROIBIDO. Coluna **`storage_key`** (relative key, nullable) é o handle canônico para delete/presign — a URL sozinha não basta (presigned expira); `key_from_url` cobre rows legados, sem backfill.
8. **Imagem**: `save_upload(mode="image")` roda sob `IMAGE_LIMITER` e rejeita canvas > 50 MP (`assert_pixel_budget`); decode só por `decode_image_bytes` (alpha preservado, `flatten_alpha` antes de JPEG/PDF/OCR). Skill `image-processing`.
9. **Delete por URL**: NUNCA com string de body/JSONB de tenant — o helper recebe `organization_id`, prova a linha em `org_uploads` da org e só apaga o storage DEPOIS do commit. Entidade que possui upload apaga também os bytes (B2) e tem job de purga do soft-delete. Skill `uploads-storage` §5b.
10. **Tamanho: request ≤ 20 MB, arquivo grande em chunks** (padrão da frota 2026-11-16, incidente: vídeo de 38 MB do iPhone tomou 413 no inbox do kailos). Os 6 domínios passam pela Cloudflare (100 MB por request, ~100 s para a origem responder → 524) e o nginx corta em 20 MB **por request, de propósito**. Arquivo > 8 MiB vai em chunks de 8 MiB para `POST/PUT/GET/DELETE /api/v1/upload-sessions` (staging em volume próprio `upload-staging`, nunca no tmpfs `/tmp` de 64 MB) e a rota de domínio recebe `file_upload_id` no lugar de `file` (dependência `make_staged_or_direct_file`). Teto por ARQUIVO no backend (`config/api.py`): **imagem 20 MB** (`IMAGE_MAX_BYTES`), **resto que só é guardado 500 MB** (`FILE_MAX_BYTES`; vídeo, PDF, documento, áudio); arquivo que o servidor lê inteiro na RAM (planilha de import, extrato, OFX, GPX, som/voz) mantém teto próprio pequeno. Rota pública sem login fica direta (≤ 18 MB). Núcleo canônico byte-idêntico: `services/uploads/upload_sessions.py` (shared-backend) + `lib/api/chunked-upload.ts`/`upload-limits.ts` (shared-widgets). Skill `uploads-storage` §9c.
11. **Nada pesado dentro do request**: transcode de vídeo, conversão longa ou envio grande a terceiro roda em background sobre a sessão (`processing → ready|failed`, cliente consulta o `GET`), porque a Cloudflare corta a resposta em ~100 s. Ex.: vídeo do WhatsApp (`POST /whatsapp/media/prepare`, bitrate pela duração para caber nos 16 MB da Meta).

## Filesystem layout

```
uploads/orgs/{org_id}/{domain}/{entity_id}/{slug}-{uuid4}.{ext}
uploads/users/{user_id}/{domain}/{entity_id}/{slug}-{uuid4}.{ext}
```

`{domain}` = constante greppable em `config/uploads.py` (`LOGOS`, `BANNERS`, `PHOTOS`, `DOCUMENTS`, `GALLERY`, …). NUNCA string concat manual de path.

## Don'ts

- **NUNCA** exportar CSV/XLSX com texto digitado por usuário sem neutralizar fórmula (CSV injection, OWASP): célula string que começa com `= + - @ TAB CR` (número puro exempto) ganha apóstrofo (`safe_cell()`, nexarena `services/registrations/registration_export_service.py`) e o xlsxwriter roda com `strings_to_formulas=False`. Copie o padrão para toda exportação dos outros apps.

- **NUNCA** `anyio.Path(...).write_bytes(...)` direto em route — sempre via `save_upload`.
- **NUNCA** gravar URL de upload fora de `org_uploads.url`/`user_uploads.url` (inline em JSONB só com row de tracking).
- **NUNCA** `orjson.loads/dumps` manual sobre `metadata` JSONB — asyncpg+Pydantic resolvem.
- **NUNCA** inferir ext sem `ext_from_name(name, mime)`.
- **NUNCA** levantar `ValueError`/`AlreadyExistsError` para MIME/size — só `BadRequestError`.
- **NUNCA** relaxar tenancy para `NULL`.
- **NUNCA** usar a **master application key** na S3 API do B2 — só restricted/multi-bucket key (keyID + appKey). Master key não funciona na S3 API.
- **NUNCA** misturar `public` e `private` no mesmo bucket B2 — acesso é bucket-wide ⇒ 2 buckets por env (público + privado).
- **NUNCA** bufferizar arquivo grande ou de tamanho desconhecido inteiro em memória para um `put_object` (PUT único vai só até 5 GB) — multipart em stream (`upload_fileobj` + `TransferConfig`, checksum `when_required`) ou arquivo temporário + `b2` CLI. Ver skill §9b. `save_upload` checa `file.size` ANTES de ler e manda `raw`/`document` > 16 MiB por `StorageBackend.save_fileobj`.
- **NUNCA** subir `client_max_body_size` (app nem gateway) para aceitar arquivo grande — a Cloudflare corta em 100 MB de qualquer jeito. Arquivo grande = sessão em chunks (invariante 10).
- **NUNCA** `await file.read()` de upload sem teto ≤ 20 MB já verificado, nem `tempfile` sem `dir=` em código de mídia (o `/tmp` do backend é tmpfs de 64 MB) — temp de mídia vai para `api_config.UPLOAD_STAGING_DIR`.
- **NUNCA** gravar nem apagar em `backups/` na raiz do bucket privado pelo código da app — é do serviço `pg-backup` (skill `database` → `backup-b2.md`).
- **NUNCA** `delete_object` simples em bucket versionado (B2 versiona por default) esperando limpar — apague TODAS as versões (`list_object_versions` + `delete_objects`), senão a história fica órfã e é cobrada.
- **NUNCA** `b2_public_base_url` = endpoint S3 cru em prod/staging — público serve via **custom domain Cloudflare** (`https://cdn.{domain}/file/{bucket}`; **um CNAME proxied** `cdn.{domain}` → `f<NNN>.backblazeb2.com` serve todos os envs pelo bucket no path), garantindo CDN + egress free (Bandwidth Alliance). Privado NUNCA passa por CDN — presigned-direto pelo gate.
- **NUNCA** criar `kind` novo sem atualizar `CHECK CONSTRAINT` + `UploadKind` enum no mesmo PR.
- **NUNCA** mutation de upload dentro do `useFileUpload` (validator-only). O envio com progresso é `useUploadMutation` (mesmo arquivo `hooks/useFileUpload.ts`) + `ApiClient.upload` (XHR, `onProgress`) — ver skill `frontend` → `file-upload.md`.
- **NUNCA** `<img src>` para `visibility != 'public'` — usar endpoint API que resolve URL (presigned em object storage privado).
