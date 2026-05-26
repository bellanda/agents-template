# Uploads & Storage — Invariantes

> **MANDATÓRIO — invocar skill `uploads-storage` ANTES de codar.**
> Toda feature que recebe arquivo do usuário, em qualquer linguagem (Python/Rust/Go)
> e qualquer storage (local NVMe / B2 / S3 / Azure / GCS). Esta rule é só o resumo
> normativo (invariantes + don'ts). API completa (`save_upload` signature, modes,
> filename regex, filesystem layout, Pydantic, repository contract, route example,
> StorageBackend Protocol) vive na skill.

## 7 invariantes universais

1. **Wrapper único** `save_upload(file, *path_parts, mode, ...)` — boundary única de IO. Nunca gravar bytes direto nem montar URL na mão.
2. **Duas tabelas** `org_uploads` (`organization_id NOT NULL`) e `user_uploads` (`owner_user_id NOT NULL`). Tenancy SEMPRE NOT NULL — zero arquivo anônimo. Cada projeto cria só a(s) tabela(s) que usa.
3. **Filename** `{slug}-{uuid4}.{ext}` — slug NFKD ASCII ≤60, uuid4 hyphenated full-length, ext lowercase.
4. **Modes** `raw | image | document` — `image` → AVIF (resize por profile, sem upscale), `document` → MIME whitelist + ext preservada, `raw` → bytes as-is.
5. **Visibility** `public | tenant | private` + `metadata.acl` — `public` = UUID4 (122 bits) é a auth; `tenant`/`private` = checagem na rota de serve.
6. **`StorageBackend`** como costura única — `save_bytes` / `delete_file` / `delete_tree` / `build_url` / `presigned_url`. Troca local ↔ object storage sem tocar business logic. Seleção via `settings.storage.backend`.
7. **Referência** via FK (single-instance: logo/banner/avatar) ou join table (multi-instance: photos/gallery/docs) → `org_uploads(id)` / `user_uploads(id)`. URL inline solta = proibido.

## Escolha rápida — tabela e padrão

| Projeto      | Tabela(s)                        | Quando                                                              |
| ------------ | -------------------------------- | ------------------------------------------------------------------- |
| org-owned    | `org_uploads`                    | tudo é da org (logo, banner, fotos, documentos)                     |
| user-owned   | `user_uploads`                   | tudo é do user (avatar, anexo de chat, export)                      |
| misto        | `org_uploads` + `user_uploads`   | mídia da org → `org_uploads`; KYC/onboarding do user → `user_uploads` |

| Referência da entidade            | Quando                                            |
| --------------------------------- | ------------------------------------------------- |
| **FK single-instance**            | Logo, banner, avatar — 1 arquivo por entidade     |
| **Join table multi-instance**     | Photos, gallery, docs — N com ordem (position)    |
| **JSONB inline + row de tracking** | Só onde domínio já é JSONB de mídia              |

## Filesystem layout

```
uploads/orgs/{org_id}/{domain}/{entity_id}/{slug}-{uuid4}.{ext}
uploads/users/{user_id}/{domain}/{entity_id}/{slug}-{uuid4}.{ext}
```

`{domain}` = constante greppable em `config/uploads.py` (`LOGOS`, `BANNERS`, `PHOTOS`, `DOCUMENTS`, `GALLERY`, …). Path via `save_upload(file, *org_dir(org_id), DOMAIN, entity_id, ...)` — nunca string concat manual.

## Visibility

- `'public'` (default) → UUID4 é a auth. Serve direto, sem JWT. ~95% dos casos.
- `'tenant'` → org_uploads: `auth.organization_id == row.organization_id`; user_uploads: `auth.user_id == row.owner_user_id`. Refinado por `metadata.acl: {roles, user_ids}`.
- `'private'` → `auth.user_id == row.owner_user_id` estrito.

Em object storage privado: presigned URL TTL curto via `GET /api/uploads/{id}/url`.

## Don'ts

- **NUNCA** `anyio.Path(...).write_bytes(file_bytes)` direto em route — sempre via `save_upload`.
- **NUNCA** gravar URL de upload em coluna que não seja `org_uploads.url` / `user_uploads.url` (inline em JSONB só com row de tracking).
- **NUNCA** `orjson.loads`/`dumps` manual sobre `metadata` ou outros JSONB — asyncpg + Pydantic já resolvem.
- **NUNCA** inferir ext sem `ext_from_name(name, mime)`.
- **NUNCA** levantar `ValueError`/`AlreadyExistsError` para MIME/size — só `BadRequestError`.
- **NUNCA** relaxar tenancy para `NULL`. Arquivo do user → `user_uploads`; da org → `org_uploads`.
- **NUNCA** criar `kind` novo sem atualizar `CHECK CONSTRAINT` + `UploadKind` enum no mesmo PR.
- **NUNCA** mutation de upload no `useFileUpload` (validator-only). Mutation custom por feature.
- **NUNCA** confiar em `<img src>` para `visibility != 'public'` — usar endpoint API que resolve URL.
