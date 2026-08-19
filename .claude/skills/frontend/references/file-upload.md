# File Upload UI — dropzone, preview, ações & validação

> Reference do gate `frontend`. Espelha no frontend o que a skill `uploads-storage` define no
> backend. Abra ANTES de construir qualquer UI de upload (arquivo/imagem/logo/banner/doc/galeria).
> **Reference impl viva: balizap** (`components/branding/` + `components/documents/`). Os utils
> puros (`useFileUpload`, `upload-error`, `file-types`) são **vendoráveis verbatim**; os componentes
> são apresentacionais (recebem callbacks) — a camada de dados (hooks/services/endpoints) é por
> projeto.

**Princípio:** upload é uma superfície com affordance clara — **dropzone** (clique OU arraste) no
estado vazio; no estado cheio o próprio asset/card É o trigger de um **menu de ações** (sem botão
three-dots solto). Validação client-side falha rápido com toast pt-BR; o servidor revalida. Delete
SEMPRE via `ConfirmDialog` central (nunca tira inline). Backend: gate `uploads-storage` / `uploads.md`.

## Tabela de decisão

| Cenário                                                          | Componente                                  |
| --------------------------------------------------------------- | ------------------------------------------- |
| Asset único de imagem (logo, banner, avatar)                    | **`ImageDropzone`** (preview + fullscreen)  |
| Documento de **título predefinido** (Termos, Política, Cardápio) | **`DocumentSlot`** (`captureTitle=false`)   |
| Documento livre com **título capturado** do usuário             | **`DocumentDropzone`** (`captureTitle=true`) |
| Lista de documentos já enviados (ações por item)                | **`DocumentList`**                          |
| Visualizar o arquivo (PDF/Office/imagem/link)                   | **`DocumentPreviewDialog`**                 |
| Captura de câmera / base64 in-place (NÃO é upload de doc)        | widget próprio (fora deste padrão)          |

## Os 2 fluxos de título (a distinção central)

- **Título predefinido** (`DocumentSlot`, `captureTitle=false`): o slot já sabe o título/categoria
  (ex.: "Termos de Uso"). Dropzone → upload direto, sem perguntar título.
- **Título capturado** (`DocumentDropzone`, `captureTitle=true`): após escolher o arquivo, um input
  inline pede o título (default = nome do arquivo sem extensão) antes de submeter. Também aceita
  **link externo** (URL) como alternativa ao arquivo.

```tsx
// Slot de título fixo — não pergunta título
<DocumentSlot title="Termos de Uso" category="terms" doc={termsDoc}
  onUpload={(f) => upload.mutate({ file: f, category: "terms" })}
  onLink={(url) => link.mutate({ url, category: "terms" })}
  onDelete={() => askDelete(termsDoc)} onPreview={openPreview}
  onCopyLink={copyLink} onDownload={download} onError={toast.error} />

// Documento livre — captura título inline
<DocumentDropzone captureTitle busy={upload.isPending}
  onUpload={(file, title) => upload.mutate({ file, title })}
  onLink={(url, title) => link.mutate({ url, title })} onError={toast.error} />
```

## Validação — `useFileUpload` (validator-only, NUNCA mutation)

Hook puro, vendorável verbatim. Retorna union discriminada pronta pra `toast.error`. A mutation é
custom por feature (ver `uploads.md` Don'ts).

```ts
const ASSET_MAX_BYTES = 5 * 1024 * 1024;
const ASSET_MIME = ["image/png", "image/jpeg", "image/webp", "image/avif"] as const;
const ASSET_EXT = [".png", ".jpg", ".jpeg", ".webp", ".avif"] as const;

const { validate } = useFileUpload({ maxBytes: ASSET_MAX_BYTES, allowedMime: ASSET_MIME, allowedExt: ASSET_EXT });
const check = validate(file); // { ok: true, file } | { ok: false, error }
if (!check.ok) return onError(check.error);
onUpload(check.file);
```

```ts
// hooks/useFileUpload.ts — canônico (vendor verbatim)
import { useCallback } from "react";

export interface UseFileUploadOptions {
  maxBytes: number;
  allowedMime: readonly string[];
  allowedExt: readonly string[]; // com ponto, lowercase
}
export type ValidationResult = { ok: true; file: File } | { ok: false; error: string };

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}
function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i < 0 ? "" : name.slice(i).toLowerCase();
}

/** Valida no browser (fail-fast + mensagem amigável). Servidor revalida. */
export function useFileUpload({ maxBytes, allowedMime, allowedExt }: UseFileUploadOptions) {
  const validate = useCallback(
    (file: File): ValidationResult => {
      if (file.size > maxBytes)
        return { ok: false, error: `Arquivo muito grande (${formatBytes(file.size)}). Máximo: ${formatBytes(maxBytes)}.` };
      const mime = (file.type || "").toLowerCase();
      if (allowedMime.length > 0 && !allowedMime.includes(mime))
        return { ok: false, error: `Tipo não suportado (${mime || "desconhecido"}). Permitido: ${allowedMime.join(", ")}.` };
      const ext = extOf(file.name);
      if (allowedExt.length > 0 && !allowedExt.includes(ext))
        return { ok: false, error: `Extensão não suportada (${ext || "desconhecida"}). Permitido: ${allowedExt.join(", ")}.` };
      return { ok: true, file };
    },
    [maxBytes, allowedMime, allowedExt]
  );
  return { validate };
}
```

## Erros do servidor — `UploadError` (normalizado, pt-BR)

Mapeia HTTP status → código discriminado + mensagem pt-BR. Idêntico entre projetos.

```ts
// lib/api/upload-error.ts — canônico (vendor verbatim)
export type UploadErrorCode =
  | "network" | "too_large" | "unsupported_type" | "unauthorized"
  | "forbidden" | "not_found" | "server" | "unknown";

const MESSAGES: Record<UploadErrorCode, string> = {
  network: "Falha de conexão. Verifique sua internet e tente novamente.",
  too_large: "Arquivo muito grande para enviar.",
  unsupported_type: "Tipo de arquivo não suportado.",
  unauthorized: "Sessão expirada. Faça login novamente.",
  forbidden: "Você não tem permissão para enviar este arquivo.",
  not_found: "Recurso não encontrado.",
  server: "Erro no servidor ao enviar o arquivo. Tente novamente.",
  unknown: "Não foi possível enviar o arquivo.",
};

export class UploadError extends Error {
  readonly code: UploadErrorCode;
  constructor(code: UploadErrorCode, message?: string) {
    super(message ?? MESSAGES[code]);
    this.name = "UploadError";
    this.code = code;
  }
  static fromUnknown(error: unknown): UploadError {
    if (error instanceof UploadError) return error;
    const status = error && typeof error === "object" && "status" in error ? Number((error as { status: unknown }).status) : undefined;
    const message = error && typeof error === "object" && "message" in error ? String((error as { message: unknown }).message) : undefined;
    if (status === 0) return new UploadError("network", message);
    if (status === 401) return new UploadError("unauthorized");
    if (status === 403) return new UploadError("forbidden");
    if (status === 404) return new UploadError("not_found");
    if (status === 413) return new UploadError("too_large");
    if (status === 415) return new UploadError("unsupported_type");
    if (status === 400) return new UploadError("unsupported_type", message);
    if (status !== undefined && status >= 500) return new UploadError("server");
    return new UploadError("unknown", message);
  }
}
```

Na mutation: `mutationFn` faz `FormData` (`file`, `title?`, `aliases?`, `category?`) e converte falha
com `throw UploadError.fromUnknown(error)`; o `onError` do `useMutation` chama `toast.error(err.message)`.

## Ícones por tipo — `file-types.ts`

`react-icons/fa6` (PDF=red, Word=blue, Excel=emerald, Texto=zinc, Markdown=violet). `fileTypeMeta`
resolve nome/ext/MIME → `{ Icon, colorClass, label, ext }` com fallback neutro. Exporta também
`ALLOWED_DOC_EXTENSIONS` / `DOC_ACCEPT_ATTR` (single source pro `accept` e o guard) e
`isAllowedDocFile(name)`. Vendor verbatim do balizap (`lib/utils/file-types.ts`); ajuste a whitelist
de extensões à do backend do projeto.

```tsx
{meta && <meta.Icon className={cn("size-6 shrink-0", meta.colorClass)} />}
```

## Menu de ações (card filled = trigger; sem three-dots)

No estado cheio, o card/imagem é o `DropdownMenuTrigger`. Itens canônicos, nesta ordem:
**Visualizar** (`Eye`/`Expand`) · **Copiar link** (`Copy`) · **Baixar** (`Download`, oculto em link
externo) · `DropdownMenuSeparator` · **Substituir** (`FileUp`, dispara `<input type="file" hidden>`)
· **Excluir** (`Trash2`, `variant="destructive"` → abre `ConfirmDialog`). Ícones de ação inline =
`lucide-react` (idiom shadcn); ícone de identidade de arquivo = `react-icons/fa6` (`file-types`).

## Preview — `DocumentPreviewDialog`

`Dialog` near-fullscreen (`h-[92vh] w-[96vw] max-w-6xl`, chromeless). PDF interno → `iframe` com
`#view=FitH`; Office (`docx/doc/xlsx/xls`) → `https://view.officeapps.live.com/op/embed.aspx?src=<url encoded>`
(precisa de URL pública); link externo → as-is; imagem → fullscreen `object-contain`. Resolva a URL
absoluta via `uploadsUrl()`.

## Resolvers de URL (padrão por projeto — `lib/utils/urls.ts`)

- `uploadsUrl(path)` — prefixa `VITE_BACKEND_URL` em paths relativos; passa http(s) absoluto direto.
- `isFileKey(v)` — `v` casa o regex UUID7 (file key não-adivinhável servida sem auth).
- `getFileApiUrl(key)` — `GET /api/v1/files/{key}`; serve como `<img src>`/href.
- `getPhotoDisplayUrl(v)` — resolve `data:` | http(s) | file key | `/api/v1/uploads/...`.

## Don'ts

- **NUNCA** mutation dentro do `useFileUpload` — é validator-only; mutation é custom por feature.
- **NUNCA** confirmar delete com tira inline/accordion/button-swap — é `ConfirmDialog` (ref `overlays.md`).
- **NUNCA** botão three-dots solto pra ações — o card/asset cheio JÁ é o trigger do menu.
- **NUNCA** inferir extensão/ícone na mão — use `fileTypeMeta` (e no backend `ext_from_name`).
- **NUNCA** `<img src>` direto pra arquivo de `visibility != "public"` — resolva via endpoint (presigned).
- **NUNCA** montar URL de upload na mão — `uploadsUrl`/`getFileApiUrl`/`getPhotoDisplayUrl`.
- **NUNCA** acoplar fetch/mutation no componente apresentacional — ele recebe callbacks; dados ficam no hook do projeto.
- **NUNCA** `accept`/whitelist divergente do backend — `DOC_ACCEPT_ATTR` espelha `ALLOWED_DOC_EXTS`.
