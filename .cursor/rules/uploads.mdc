# Uploads & Storage — Invariantes

> **MANDATÓRIO — invocar skill `uploads-storage` ANTES de codar.** Qualquer upload (arquivo/imagem/doc/mídia/áudio/vídeo/export) em qualquer linguagem (Python/Rust/Go) e qualquer storage (local NVMe / B2 / S3 / Azure / GCS). Esta rule é só invariantes + don'ts; API completa (`save_upload`, modes, filename regex, layout, Pydantic, repository, `StorageBackend` Protocol) na skill.

## Invariantes universais

1. **Wrapper único** `save_upload(file, *path_parts, mode, ...)` — boundary única de IO. Nunca grave bytes direto, nunca monte URL na mão.
2. **Duas tabelas, tenancy NOT NULL**: `org_uploads(organization_id)` e `user_uploads(owner_user_id)`. Zero arquivo anônimo. Projeto cria só a(s) que usa.
3. **Filename**: `{slug}-{uuid4}.{ext}` — slug NFKD ASCII ≤60, uuid4 hyphenated full-length, ext lowercase via `ext_from_name(name, mime)`.
4. **Modes**: `raw` (bytes as-is) | `image` (→ AVIF, resize por profile, sem upscale) | `document` (MIME whitelist + ext preservada).
5. **Visibility** + `metadata.acl`: `public` (UUID4 122 bits é a auth, ~95% dos casos) | `tenant` (org/user check) | `private` (owner only).
6. **`StorageBackend` Protocol**: `save_bytes` / `delete_file` / `delete_tree` / `build_url` / `presigned_url`. Troca local ↔ object storage sem tocar business. Seleção via `settings.storage.backend`.
7. **Referência**: FK single-instance (logo/banner/avatar) OU join table multi-instance (photos/gallery/docs) → `org_uploads(id)`/`user_uploads(id)`. URL inline solta = PROIBIDO.

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
- **NUNCA** criar `kind` novo sem atualizar `CHECK CONSTRAINT` + `UploadKind` enum no mesmo PR.
- **NUNCA** mutation de upload no `useFileUpload` (validator-only). Mutation custom por feature.
- **NUNCA** `<img src>` para `visibility != 'public'` — usar endpoint API que resolve URL (presigned em object storage privado).
