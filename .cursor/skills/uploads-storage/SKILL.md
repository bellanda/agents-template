---
name: uploads-storage
description: Padrão UNIVERSAL de uploads e storage para QUALQUER projeto/linguagem (Python, Rust, Go) e QUALQUER storage (filesystem local NVMe, BackBlaze B2, AWS S3, Azure Blob, GCS) — wrapper save_upload, duas tabelas org_uploads/user_uploads, filename {slug}-{uuid4}, modes raw/image/document, image→AVIF, FK single-instance vs join table, visibility public/tenant/private + ACL, abstração StorageBackend, serving UUID-público vs auth-gated. INVOCAR SEMPRE antes de escrever qualquer código de upload (arquivo/imagem/documento/mídia/áudio/vídeo/export), criar nova `kind`, modelar entidade com upload, ou planejar migração local → object storage. Complementa skill `image-processing` (OpenCV/AVIF puro).
---

# Uploads & Storage — Padrão Universal

**Este é o contrato único de uploads para todos os projetos, em qualquer linguagem e qualquer storage.** Não re-derive nada: siga o contrato universal (§0), use o eixo de storage (§Storage) como costura, e copie a implementação de referência em Python (§1–§10) ou o contrato idiomático em Rust (§Rust) / Go (§Go).

Wrapper canônico `save_upload` + duas tabelas `org_uploads` / `user_uploads` resolvem 100% dos casos. Toda rota/handler que aceita um arquivo deve: validar → `save_upload` → criar row na tabela correta → referenciar via FK/join na entidade dona. **Escolha da tabela:** arquivo da organização → `org_uploads` (`organization_id NOT NULL`); arquivo do usuário antes/fora de qualquer org → `user_uploads` (`owner_user_id NOT NULL`). Cada projeto cria só a(s) tabela(s) que usa (projeto org-owned→`org_uploads`; user-owned→`user_uploads`; misto→ambas). Invariantes normativos vivem na rule **`uploads.md`**.

## 0. Contrato universal (language- & storage-agnostic)

O que NÃO muda entre linguagens nem entre backends de storage:

| Invariante           | Regra                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------ |
| **Wrapper único**    | `save_upload(file, *path_parts, mode, ...)` — boundary única de IO. Nunca gravar bytes/URL na mão.     |
| **Duas tabelas**     | `org_uploads` (`organization_id NOT NULL`) + `user_uploads` (`owner_user_id NOT NULL`). Tenancy SEMPRE NOT NULL — todo upload tem dono, zero anônimo. |
| **Filename**         | `{slug}-{uuid4}.{ext}` — slug NFKD ASCII ≤60, uuid4 hyphenated, ext lowercase.                          |
| **Modes**            | `raw` (bytes as-is) · `image` (→AVIF, resize por profile, sem upscale) · `document` (MIME whitelist + ext preservada). |
| **Visibility**       | `public` (UUID4 122-bit é a auth) · `tenant` · `private` + `metadata.acl`.                              |
| **StorageBackend**   | `save_bytes` / `delete_file` / `delete_tree` / `build_url` / `presigned_url`. Costura local↔object.     |
| **Referência**       | FK single-instance OU join table multi-instance → `org_uploads(id)` / `user_uploads(id)`. URL inline solta = proibido. |
| **Layout em disk/key** | `orgs/{org_id}/{domain}/{entity_id}/...` ou `users/{user_id}/{domain}/{entity_id}/...`.               |

Decisões rápidas:
- **org vs user** → o arquivo é da organização (logo, foto de veículo, banner de evento) ou do usuário antes de existir org (KYC do organizador, avatar)? Org → `org_uploads`; user → `user_uploads`.
- **single FK vs join table** → entidade tem 0/1 do asset → coluna FK; tem N (ordem importa) → join table com `position`.
- **public vs tenant/private** → o conteúdo vaza algo sensível mesmo sem identificar pessoa (CPF, contrato, doc pendente)? Não → `public`; sim → `tenant`/`private` + serve auth-gated.
- **local vs object storage** → hoje sempre local; a migração é trocar a impl do `StorageBackend` (B2/S3/Azure/GCS), nunca a assinatura.

## Eixo storage — `StorageBackend` é a costura única

Toda IO de bytes passa por um `StorageBackend`. Hoje `LocalStorageBackend` (NVMe); amanhã object storage, **sem tocar business logic**.

```python
class StorageBackend(Protocol):
    async def save_bytes(self, key: str, content: bytes, mime: str | None) -> str: ...
    async def delete_file(self, key: str) -> bool: ...
    async def delete_tree(self, prefix: str) -> bool: ...
    def build_url(self, key: str) -> str: ...                                    # URL pública estável
    async def presigned_url(self, key: str, ttl_seconds: int = 600) -> str: ...  # acesso privado
```

| Backend                          | Implementação                                                       | `public`                          | `tenant`/`private`            |
| -------------------------------- | ------------------------------------------------------------------- | --------------------------------- | ----------------------------- |
| `LocalStorageBackend` (hoje)     | grava em `UPLOADS_DIR`, serve via nginx/handler                     | URL estável                       | handler valida auth, serve    |
| `B2BackBlazeStorage`             | S3-compatible, endpoint B2 (`aioboto3`/`aws-sdk-*`)                 | bucket público + CDN              | bucket privado + presigned    |
| `S3StorageBackend` (AWS)         | mesma API S3                                                        | bucket público + CloudFront       | bucket privado + presigned    |
| `AzureBlobStorageBackend`        | Azure SDK                                                           | container público                 | SAS URL TTL curto             |
| `GcsStorageBackend`              | GCS SDK                                                             | bucket público                    | signed URL TTL curto          |

Seleção por `settings.storage.backend`. `B2BackBlazeStorage` é só uma config (endpoint) do backend S3-compatible. **B2/object storage = trabalho seguinte** — hoje os projetos carregam só um `# TODO(b2)` no `config/uploads.py` na costura; não implementar agora.

---

# Python — implementação de referência

> Copiável as-is (FastAPI + asyncpg + Pydantic + OpenCV + anyio). Em Rust/Go, ver §Rust e §Go — o contrato é o mesmo.

## 1. Decidir o `mode`

```python
# Imagem (qualquer formato in, AVIF out, resize por profile)
result = await save_upload(
    file, *org_dir(org_id), VEHICLES, vehicle_id, PHOTOS,
    mode="image",
    image_profile="full_hd",   # ou "hd" / "original"
)

# Documento (preserva ext, valida MIME whitelist, respeita size cap)
result = await save_upload(
    file, *org_dir(org_id), VEHICLES, vehicle_id, DOCUMENTS,
    base_name="crlv",
    mode="document",
    allowed_mime={"application/pdf"},          # override do default
    max_bytes=api_config.DOCUMENT_MAX_BYTES,
)

# Raw (bytes as-is, sem processamento — WhatsApp media, exports)
result = await save_upload(
    file, *org_dir(org_id), WHATSAPP, WHATSAPP_IN, conversation_id,
    mode="raw",
)

# User-owned (precede qualquer org — ex: KYC/onboarding do usuário)
result = await save_upload(
    file, *user_dir(user_id), ORGANIZER_REQUESTS,
    mode="document",
    allowed_mime={"application/pdf", "image/jpeg", "image/png"},
)
```

Critical:
- `mode="image"` força ext `.avif` e roda OpenCV → resize → encode em thread pool. Quality fixa `AVIF_QUALITY=80`.
- `mode="document"` SEM `allowed_mime=` usa `DEFAULT_DOCUMENT_MIME_WHITELIST` (PDF, Office, txt, md, csv, json, rtf). Whitelist customizada substitui.
- `mode="raw"` NÃO valida MIME nem força ext. Reservar para casos onde o caller já validou ou o tipo é arbitrário (WhatsApp inbound, exports gerados pela app).
- `*org_dir(id)` → `orgs/{id}/...`; `*user_dir(id)` → `users/{id}/...`. Nunca string concat manual de path.

## 2. Persistir em `org_uploads` / `user_uploads`

Sempre depois do `save_upload`, criar a row no DB. Org-owned:

```python
file_record = OrgUpload(
    organization_id=org_id,                 # NOT NULL
    owner_user_id=auth.user_id,             # atribuição/ACL, opcional
    entity_type="vehicles",
    entity_id=str(vehicle_id),
    kind=UploadKind.PHOTO,
    url=result.url,
    filename=result.filename,
    mime_type=result.mime_type,
    size_bytes=result.size_bytes,
    width=result.width,
    height=result.height,
    visibility=UploadVisibility.PUBLIC,
)
created = await org_upload_repository.create(conn, file_record)
file_id = created["id"]
```

User-owned é idêntico, trocando `OrgUpload`/`org_upload_repository` por `UserUpload`/`user_upload_repository` e usando `owner_user_id=user_id` (sem `organization_id`). Depois, ligar à entidade:

```python
# Single-instance (logo, banner, avatar, crlv): UPDATE da coluna FK
await organization_repository.update(conn, org_id, {"logo_id": file_id})

# Multi-instance (photos, gallery, documents): INSERT na join table
await vehicle_photo_repository.create(
    conn, vehicle_id=vehicle_id, file_id=file_id, position=next_position,
)
```

## 3. Single FK vs Join Table — como decidir

| Sinal                                              | Use                                                              |
| -------------------------------------------------- | ---------------------------------------------------------------- |
| Entidade tem 0 ou 1 desse asset                    | Coluna FK `{kind}_id UUID NULL REFERENCES org_uploads(id) ON DELETE SET NULL` |
| Entidade tem N do mesmo kind, ordem importa        | Join table `{entity}_files(entity_id, file_id, position, ...)` com `ON DELETE CASCADE` |
| Entidade tem N de kinds diferentes (docs + media)  | Uma join table por kind, ou uma join table com coluna `kind_subtype TEXT` |
| Você está tentado a fazer `JSONB[]` de file inline | **Pare.** Sempre FK (ou, onde o domínio já é JSONB, row de tracking via registrar). |

> FK aponta para `org_uploads(id)` em projetos/casos org-owned e `user_uploads(id)` em casos user-owned (ex: avatar de usuário → `user_uploads`).

Exemplo single-instance:
```sql
ALTER TABLE organizations
    ADD COLUMN logo_id   UUID NULL REFERENCES org_uploads(id) ON DELETE SET NULL,
    ADD COLUMN banner_id UUID NULL REFERENCES org_uploads(id) ON DELETE SET NULL;
```

Exemplo multi-instance:
```sql
CREATE TABLE vehicle_photos (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id  UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    file_id     UUID NOT NULL REFERENCES org_uploads(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_vehicle_photos_vehicle_id ON vehicle_photos(vehicle_id);
CREATE INDEX ix_vehicle_photos_file_id ON vehicle_photos(file_id);
```

Critical:
- Join table com `ON DELETE CASCADE` no `entity_id` E no `file_id`: deletar entidade dona limpa join + a tabela de upload. Deletar a row de upload direto limpa as referências (raro, mas previne dangling).
- Single-instance: `ON DELETE SET NULL` no `{kind}_id` para que delete da row de upload apenas zere a referência (não delete a entidade dona).

## 4. Replace pattern — substituir asset existente

Padrão em logos/banners/avatars: user sobe nova versão, antiga deve ser deletada (DB row + arquivo no disk).

```python
async def update_organization_logo(conn, org_id: UUID, file: UploadFile, auth: AuthContext):
    # 1. Carrega referência antiga
    org = await organization_repository.find_by_id(conn, org_id)
    previous_file_id = org.get("logo_id")

    # 2. Salva nova
    result = await save_upload(
        file, *org_dir(org_id), LOGOS,
        fixed_name="logo",
        mode="image",
        image_profile="full_hd",
    )
    new_record = OrgUpload(...)
    created = await org_upload_repository.create(conn, new_record)

    # 3. Atualiza FK na entidade
    await organization_repository.update(conn, org_id, {"logo_id": created["id"]})

    # 4. Limpa antiga (DB + disk)
    if previous_file_id:
        previous = await org_upload_repository.find_by_id(conn, previous_file_id)
        if previous:
            await delete_file_by_url(previous["url"])
            await org_upload_repository.hard_delete(conn, previous_file_id)

    return OrgUploadResponse(**created)
```

Critical:
- Ordem: salva nova → atualiza FK → deleta antiga. Se algo falhar no meio, FK aponta para arquivo válido; pior caso = órfão na tabela de upload (limpado por background job).
- NUNCA delete a antiga primeiro — falha no upload deixa entidade sem asset.

## 5. Delete cascade na entidade

Quando a entidade dona é deletada, queremos limpar arquivos físicos. FK CASCADE cuida do DB; arquivos no disk precisam de ação explícita:

```python
async def delete_vehicle(conn, vehicle_id: UUID, auth: AuthContext):
    # Pega URLs/IDs ANTES do delete (CASCADE vai apagar a row)
    photos = await org_upload_repository.find_by_entity(conn, "vehicles", str(vehicle_id))

    # Delete da entidade — CASCADE limpa vehicle_photos + org_uploads
    await vehicle_repository.hard_delete(conn, vehicle_id)

    # Limpa arquivos no disk (best-effort, fora da transação)
    await delete_directory(*org_dir(auth.organization_id), VEHICLES, str(vehicle_id))
```

Alternativa para domínios sensíveis: pegar URL by URL antes do CASCADE e chamar `delete_file_by_url` para cada. `delete_directory` é atalho quando todo o `{entity}/{entity_id}/` pode ir embora.

## 6. Adicionar nova `kind`

`kind` tem CHECK CONSTRAINT que espelha o `UploadKind` StrEnum, **em cada tabela que o projeto cria** (`org_uploads` e/ou `user_uploads`). Adicionar valor é mudança no mesmo PR:

1. **Migration** ALTER do CHECK (repetir para `user_uploads` se o projeto a tiver):
   ```sql
   ALTER TABLE org_uploads
       DROP CONSTRAINT ck_org_uploads_kind,
       ADD CONSTRAINT ck_org_uploads_kind CHECK (kind IN (
           'logo','banner','avatar','photo','gallery_image','document',
           'attachment','whatsapp_media','export','other',
           'invoice'   -- novo
       ));
   ```
2. **StrEnum** em `models/uploads/upload_jsonb.py`:
   ```python
   class UploadKind(StrEnum):
       ...
       INVOICE = "invoice"
   ```
3. **Repository / route** que cria a row com o novo kind.

Bater tudo = sem schema drift (`check_schema.py` valida `OrgUpload`↔`org_uploads`, `UserUpload`↔`user_uploads`).

## 7. Visibility e ACL — quando ativar

Default: tudo é `visibility="public"`. UUID4 unguessable (122 bits) é a "auth" e a rota `/uploads/...` serve sem JWT check.

Subir para `'tenant'` quando o arquivo carrega dados que vazariam mesmo sem identificação de pessoa: CRLV (CPF), contrato (cláusulas), documento de organizer pendente de aprovação.

```python
file_record = OrgUpload(
    ...,
    visibility=UploadVisibility.TENANT,
    metadata=UploadMetadata(
        acl=UploadAcl(roles=["admin", "finance"]),    # opcional: refinamento dentro da org
    ),
)
```

Subir para `'private'` quando só o owner pode acessar (export pessoal, draft pré-publicação).

A rota `/uploads/{path}` resolve a tabela pelo prefixo do path (`orgs/` → `org_uploads`, `users/` → `user_uploads`), carrega a row pelo `url`/path, e aplica:

```python
async def serve_upload(conn, url_path: str, auth: AuthContext) -> Response:
    repo = org_upload_repository if url_path.startswith("orgs/") else user_upload_repository
    row = await repo.find_by_url(conn, url_path)
    if not row:
        raise NotFoundError(...)

    if row["visibility"] == "tenant":
        if "organization_id" in row and auth.organization_id != row["organization_id"]:
            raise ForbiddenError(...)
        acl = (row["metadata"] or {}).get("acl") or {}
        if acl.get("roles") and not (set(auth.roles) & set(acl["roles"])):
            raise ForbiddenError(...)
        if acl.get("user_ids") and str(auth.user_id) not in acl["user_ids"]:
            raise ForbiddenError(...)
    elif row["visibility"] == "private":
        if auth.user_id != row["owner_user_id"]:
            raise ForbiddenError(...)

    return FileResponse(...)
```

Em B2: bucket privado + endpoint `GET /api/uploads/{id}/url` que retorna presigned URL TTL 5-10 min depois de passar pelos checks acima.

## 8. Migration checklist — local FS → object storage (B2 / S3 / Azure / GCS)

**Trabalho seguinte — não fazer agora.** Hoje os projetos só carregam um `# TODO(b2)` no `config/uploads.py` na costura de IO. Quando for a hora:

1. **Config**:
   - Adicionar `storage:` block em `config/app/{env}.yaml`: `backend: "local" | "b2" | "s3" | "azure" | "gcs"`, bucket público/privado, endpoint/region.
   - Secrets do provider em `.env.example` (vazias) — `B2_KEY_ID`/`B2_APP_KEY`, `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `AZURE_STORAGE_CONNECTION_STRING`, `GCS_*`. Popular `.env` local manualmente.
   - Sub-model `StorageSettings` em `config/settings.py`.
2. **Interface** (a costura única — ver §Storage):
   ```python
   class StorageBackend(Protocol):
       async def save_bytes(self, key: str, content: bytes, mime: str | None) -> str: ...
       async def delete_file(self, key: str) -> bool: ...
       async def delete_tree(self, prefix: str) -> bool: ...
       def build_url(self, key: str) -> str: ...
       async def presigned_url(self, key: str, ttl_seconds: int = 600) -> str: ...
   ```
3. **Implementações**:
   - `LocalStorageBackend` — extrai a lógica atual de `save_upload` (mkdir + write_bytes; delete via unlink/rmtree).
   - `B2BackBlazeStorage` / `S3StorageBackend` — S3-compatible via `aioboto3`/`aiobotocore`; B2 = endpoint custom.
   - `AzureBlobStorageBackend` / `GcsStorageBackend` — SDK do provider; presigned = SAS / signed URL.
4. **Factory em `config/uploads.py`** (selecionada por `settings.storage.backend`):
   ```python
   storage: StorageBackend = build_storage_backend(settings.storage)
   ```
   `save_upload` chama `storage.save_bytes(key, content, mime)` no fim — sem mudar a assinatura externa. Deletes passam por `storage.delete_file` / `storage.delete_tree`.
5. **URL resolution**:
   - `visibility='public'` → `build_url(key)` (URL estável do bucket público).
   - `visibility != 'public'` → endpoint `GET /api/uploads/{id}/url` retorna `presigned_url` com TTL curto.
6. **Migration de dados** (se em prod): script que sobe os arquivos locais para o bucket + atualiza `org_uploads.url` / `user_uploads.url` em batch. Em dev: reset + reupload manual.
7. **Cleanup deletes**: object storage não tem `rmtree`. `delete_tree` enumera objects do prefix e deleta em pipeline/batch.
8. **CDN**: Cloudflare/CloudFront na frente do bucket público. DNS aponta `cdn.dominio.com` para o endpoint do provider.

## 9. Frontend — hook e mutation

```typescript
// 1. Validator (sempre, idêntico nos 3 projetos)
const { validate } = useFileUpload({
  maxBytes: 10 * 1024 * 1024,
  allowedMime: ["image/png", "image/jpeg", "image/webp"],
  allowedExt: [".png", ".jpg", ".jpeg", ".webp"],
});

// 2. Mutation customizada por feature (TanStack Query)
const uploadLogoMutation = useMutation({
  mutationFn: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await client.post<OrgUploadResponse>(
      `/organizations/${orgId}/branding/logo`, form
    );
    return res.data;
  },
  onSuccess: (data) => { ... },
  onError: (err: UploadError) => toast.error(err.message),
});

// 3. Handler
const onPick = async (file: File) => {
  const check = validate(file);
  if (!check.ok) { toast.error(check.error); return; }
  await uploadLogoMutation.mutateAsync(check.file);
};
```

Para chat de agente: hook dedicado `useChatFileUpload` com mutation embutida + sessionId/modelId.

## 10. Pitfalls

- **Nunca** `orjson.loads`/`orjson.dumps` manual sobre `metadata` JSONB — asyncpg + Pydantic já resolvem.
- **Nunca** levantar `ValueError`/`AlreadyExistsError` para MIME inválido. Sempre `BadRequestError`.
- **Nunca** confiar em `file.content_type` sem validação — browsers mandam o que quiserem. Whitelist é defesa.
- **Nunca** relaxar a coluna de tenancy para `NULL` — arquivo do usuário vai em `user_uploads`, da org em `org_uploads`.
- **Nunca** colocar mutation no `useFileUpload` (validator-only).
- **Nunca** servir arquivo `visibility != 'public'` direto pelo nginx sem passar pelo gate da API.
- **Nunca** ON DELETE CASCADE em todas as FKs sem pensar — replace pattern requer cascade controlado.
- **Trigger de `updated_at`** em `org_uploads`/`user_uploads` é gerenciado pelo `update_updated_at_column()` BEFORE UPDATE. NUNCA setar `updated_at` em UPDATE manual.
- **`avif_quality`** está fixa em 80 (constante `AVIF_QUALITY`). Não parametrizar por call — uniformidade > flexibilidade.
- **`fixed_name`** vs `base_name`: ambos viram slug. `fixed_name` é semântico ("logo", "banner"), `base_name` aceita o filename do user. Use `fixed_name` para single-instance e `base_name` para multi-instance.

---

# Rust — contrato idiomático

Mesmo contrato (§0), idioma Rust. Sem app inteiro — assinaturas + decisões.

**Libs:** `axum`/`actix-web` (multipart), `sqlx` (Postgres, `org_uploads`/`user_uploads`), `image` + `ravif` (ou `libavif-sys`) p/ AVIF, `aws-sdk-s3` (B2/S3 — endpoint custom p/ B2), `uuid`, `unicode-normalization` (slug NFKD), `tokio`.

```rust
#[async_trait::async_trait]
pub trait StorageBackend: Send + Sync {
    async fn save_bytes(&self, key: &str, content: &[u8], mime: Option<&str>) -> anyhow::Result<String>;
    async fn delete_file(&self, key: &str) -> anyhow::Result<bool>;
    async fn delete_tree(&self, prefix: &str) -> anyhow::Result<bool>;
    fn build_url(&self, key: &str) -> String;
    async fn presigned_url(&self, key: &str, ttl: std::time::Duration) -> anyhow::Result<String>;
}

pub struct LocalStorage { base: std::path::PathBuf, http_prefix: String }
pub struct B2BackBlazeStorage { /* aws_sdk_s3::Client + buckets */ }  // TODO: depois

pub enum Mode { Raw, Image, Document }

pub struct UploadResult {
    pub url: String, pub filename: String,
    pub mime_type: Option<String>, pub size_bytes: i64,
    pub width: Option<i32>, pub height: Option<i32>,
}

// validate → (encode AVIF se Image) → storage.save_bytes(key, &bytes, mime)
pub async fn save_upload(/* field multipart, path_parts: &[&str], mode: Mode, opts */)
    -> Result<UploadResult, UploadError> { todo!() }
```

**Filename:** `slugify` = NFKD → ASCII lower → `[a-z0-9]+`→`-`, ≤60, + `Uuid::new_v4()` + ext lower.
**Gotchas:**
- Multipart é **streaming**: leia em chunks com cap (`http_body`/`axum` limit), enforce `max_bytes` enquanto lê — não bufferize ilimitado.
- Encode de imagem (`image`+`ravif`) é CPU-bound → `tokio::task::spawn_blocking`. Nunca no executor async.
- MIME: whitelist + sniff (`infer` crate) p/ documentos; `Content-Type` do cliente é hint, não confiança.
- `sqlx` JSONB (`metadata`) via `sqlx::types::Json<T>` — sem serde manual no boundary do DB.
- MIME/size inválido → 400, nunca 500.

---

# Go — contrato idiomático

Mesmo contrato (§0), idioma Go.

**Libs:** `net/http` (ou `echo`/`chi`) p/ multipart, `pgx` (Postgres, `org_uploads`/`user_uploads`), AVIF via `github.com/gen2brain/avif` (ou cgo `libavif`; `disintegration/imaging` p/ resize), `aws-sdk-go-v2/s3` (B2/S3), `github.com/google/uuid`, `golang.org/x/text/unicode/norm` (slug NFKD).

```go
type StorageBackend interface {
    SaveBytes(ctx context.Context, key string, content []byte, mime string) (string, error)
    DeleteFile(ctx context.Context, key string) (bool, error)
    DeleteTree(ctx context.Context, prefix string) (bool, error)
    BuildURL(key string) string
    PresignedURL(ctx context.Context, key string, ttl time.Duration) (string, error)
}

type LocalStorage struct{ Base, HTTPPrefix string }
type B2BackBlazeStorage struct{ /* s3.Client + buckets */ } // TODO: depois

type Mode string
const ( ModeRaw Mode = "raw"; ModeImage Mode = "image"; ModeDocument Mode = "document" )

type UploadResult struct {
    URL, Filename string
    MimeType      *string
    SizeBytes     int64
    Width, Height *int
}

// open → enforce max_bytes → (AVIF encode se Image) → storage.SaveBytes
func SaveUpload(ctx context.Context, fh *multipart.FileHeader, pathParts []string, mode Mode) (UploadResult, error) {
    panic("todo")
}
```

**Filename:** slug = NFKD → ASCII lower → `[a-z0-9]+`→`-`, ≤60, + `uuid.NewString()` + ext lower.
**Gotchas:**
- `http.MaxBytesReader` + `r.ParseMultipartForm(maxMemory)` — cap explícito de tamanho.
- Encode/resize de imagem é CPU-bound → goroutine/worker pool; não bloqueie o handler em lote.
- MIME: `http.DetectContentType` (sniff 512 bytes) + whitelist; `Content-Type` do cliente é hint.
- `pgx` JSONB (`metadata`) via `json.RawMessage`/`pgtype` — sem marshalling fora do boundary.
- MIME/size inválido → 400, nunca 500.

---

# Decision trees

**Qual tabela?**
```
arquivo pertence a uma organização?
  ── sim ─────────────────────────────▶ org_uploads  (organization_id NOT NULL)
  └── não (do usuário, talvez antes de org) ─▶ user_uploads (owner_user_id NOT NULL)
```

**Single FK vs join table?**
```
entidade tem no máximo 1 desse asset?
  ── sim ───────────────────────────▶ coluna FK {kind}_id  (ON DELETE SET NULL)
  └── N do mesmo kind (ordem importa) ─▶ join table {entity}_files(file_id, position)  (ON DELETE CASCADE)
```

**public vs tenant/private?**
```
o conteúdo vaza algo sensível mesmo sem identificar a pessoa? (CPF, contrato, doc pendente)
  ── não ───────────────────────────────▶ public   (UUID4 122-bit é a auth; serve direto)
  ── sim, qualquer um da org/tenant vê ──▶ tenant   (+ metadata.acl p/ refinar)
  └── sim, só o dono ────────────────────▶ private
```

**local vs object storage?**
```
hoje ─▶ sempre LocalStorageBackend (NVMe).
migração ─▶ trocar a impl do StorageBackend (B2/S3/Azure/GCS), NUNCA a assinatura de save_upload. Ver §8.
```

---

# Pitfalls — universais (toda linguagem / todo storage)

- **Nunca** gravar bytes/URL fora de `save_upload` + `StorageBackend`. Boundary única de IO.
- **Nunca** tenancy `NULL` — arquivo do user → `user_uploads`, da org → `org_uploads`. Zero anônimo/untracked.
- **Nunca** confiar no `Content-Type` do cliente — whitelist (+ sniff) é a defesa.
- **Nunca** encodar/redimensionar imagem no executor async/handler — sempre thread/goroutine dedicada (CPU-bound).
- **Nunca** URL de upload inline solta — sempre FK/join → `org_uploads(id)` / `user_uploads(id)`.
- **Nunca** servir `visibility != 'public'` direto (nginx/bucket público) sem passar pelo gate de auth.
- **Nunca** MIME/size inválido como 500 — é 400 (bad request).
- **Nunca** criar `kind` nova sem atualizar o CHECK constraint (em cada tabela do projeto) + o enum no mesmo PR.
- AVIF quality fixa (80); slug ≤60 + uuid4 full-length sempre. Uniformidade > flexibilidade.
