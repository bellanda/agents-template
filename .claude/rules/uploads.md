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
6. **`StorageBackend` Protocol**: `save_bytes` / `delete_file` / `delete_tree` / `build_url` / `presigned_url` / `key_from_url` + flag `is_remote`. Troca local ↔ object storage sem tocar business. Seleção via `settings.storage.backend`. **Hint `public: bool`** em `save_bytes`/`delete_file`/`build_url` roteia o bucket (público vs privado) no backend remoto; o local ignora. `delete_tree` NÃO tem hint (um subtree pode misturar visibilities → limpa ambos os buckets). Serving ramifica em `is_remote`: local → `FileResponse`; remoto → **presigna (private bucket) + 302 redirect**.
7. **Referência**: FK single-instance (logo/banner/avatar) OU join table multi-instance (photos/gallery/docs) → `org_uploads(id)`/`user_uploads(id)`. URL inline solta = PROIBIDO. Coluna **`storage_key`** (relative key, nullable) é o handle canônico para delete/presign — a URL sozinha não basta (presigned expira); `key_from_url` cobre rows legados, sem backfill.

## Filesystem layout

```
uploads/orgs/{org_id}/{domain}/{entity_id}/{slug}-{uuid4}.{ext}
uploads/users/{user_id}/{domain}/{entity_id}/{slug}-{uuid4}.{ext}
```

`{domain}` = constante greppable em `config/uploads.py` (`LOGOS`, `BANNERS`, `PHOTOS`, `DOCUMENTS`, `GALLERY`, …). NUNCA string concat manual de path.

## Don'ts

- **NUNCA** `anyio.Path(...).write_bytes(...)` direto em route — sempre via `save_upload`.
- **NUNCA** gravar URL de upload fora de `org_uploads.url`/`user_uploads.url` (inline em JSONB só com row de tracking).
- **NUNCA** `orjson.loads/dumps` manual sobre `metadata` JSONB — asyncpg+Pydantic resolvem.
- **NUNCA** inferir ext sem `ext_from_name(name, mime)`.
- **NUNCA** levantar `ValueError`/`AlreadyExistsError` para MIME/size — só `BadRequestError`.
- **NUNCA** relaxar tenancy para `NULL`.
- **NUNCA** usar a **master application key** na S3 API do B2 — só restricted/multi-bucket key (keyID + appKey). Master key não funciona na S3 API.
- **NUNCA** misturar `public` e `private` no mesmo bucket B2 — acesso é bucket-wide ⇒ 2 buckets por env (público + privado).
- **NUNCA** `delete_object` simples em bucket versionado (B2 versiona por default) esperando limpar — apague TODAS as versões (`list_object_versions` + `delete_objects`), senão a história fica órfã e é cobrada.
- **NUNCA** `b2_public_base_url` = endpoint S3 cru em prod/staging — público serve via **custom domain Cloudflare** (`https://cdn.{domain}/file/{bucket}`; **um CNAME proxied** `cdn.{domain}` → `f<NNN>.backblazeb2.com` serve todos os envs pelo bucket no path), garantindo CDN + egress free (Bandwidth Alliance). Privado NUNCA passa por CDN — presigned-direto pelo gate.
- **NUNCA** criar `kind` novo sem atualizar `CHECK CONSTRAINT` + `UploadKind` enum no mesmo PR.
- **NUNCA** mutation de upload no `useFileUpload` (validator-only). Mutation custom por feature.
- **NUNCA** `<img src>` para `visibility != 'public'` — usar endpoint API que resolve URL (presigned em object storage privado).
