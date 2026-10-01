# File Upload UI — dropzone, preview, ações, progresso & validação

> Reference do gate `frontend`. Espelha no frontend o que a skill `uploads-storage` define no
> backend. Abra ANTES de construir qualquer UI de upload (arquivo/imagem/logo/banner/doc/galeria).
> **Canônico (2026-10-01): promoservice** — `components/uploads/*` (`DocumentDropzone`,
> `DocumentSlot`, `DocumentList`, `DocumentPreviewDialog`, `PhotoGallery`, `UploadProgress`),
> `components/branding/ImageDropzone.tsx`, `hooks/useFileUpload.ts` (`useFileUpload` +
> `useUploadMutation`), `lib/api/client.ts` (`ApiClient.upload`), `lib/utils/image-compress.ts`,
> `lib/utils/file-types.ts`. Kailos já vendora `hooks/useFileUpload.ts` + `components/uploads/{DocumentDropzone,DocumentSlot,UploadProgress}.tsx`. O `DocumentSlot` nasceu no **balizap** (`components/documents/
> DocumentSlot.tsx`) e foi adaptado aos primitivos do promoservice. Os utils puros (`validate`,
> `upload-error`, `file-types`) são **vendoráveis verbatim**; os componentes são apresentacionais
> (recebem callbacks) — a camada de dados (hooks/services/endpoints) é por projeto.

**Princípio:** upload é uma superfície com affordance clara — **dropzone** (clique OU arraste) no
estado vazio; no estado cheio o próprio asset/card É o trigger de um **menu de ações** (sem botão
three-dots solto). Validação client-side falha rápido com toast pt-BR; o servidor revalida. Todo
envio com espera visível mostra **progresso real**. Delete SEMPRE via `ConfirmDialog` central (nunca
tira inline). Backend: gate `uploads-storage` / `uploads.md`.

## Tabela de decisão

| Cenário                                                           | Componente (canônico promoservice)                              |
| ----------------------------------------------------------------- | --------------------------------------------------------------- |
| Asset único de imagem (logo, banner, avatar)                      | **`ImageDropzone`** (preview + fullscreen + menu)               |
| Várias fotos de uma entidade (OS, veículo, check-list)            | **`PhotoGallery`** (+ `compressImage`, ver "Redução no navegador") |
| Documento de **título predefinido** (Termos, CNH, Orçamento assinado) | **`DocumentSlot`** (single-instance; subir de novo troca)   |
| Anexo solto, sem título/slot (lista de anexos da entidade)        | `DocumentDropzone` (`onSelect(file)`) + `DocumentList`          |
| Visualizar o arquivo (PDF/Office/imagem)                          | **`DocumentPreviewDialog`**                                     |
| Documento livre com **título capturado** do usuário e/ou **link externo** | variante do **balizap** (`DocumentDropzone captureTitle` + `onLink`) — só onde o produto exige |
| Arquivos escolhidos **antes** da entidade existir (form de criação) | variante **nexarena** (seção abaixo)                          |
| Captura de câmera / base64 in-place (NÃO é upload de doc)         | widget próprio (fora deste padrão)                              |

## Os 2 fluxos de título (a distinção central)

- **Título predefinido** (`DocumentSlot`): o slot já sabe o título/categoria (ex.: "Termos de Uso").
  Dropzone → upload direto, sem perguntar título. O `DocumentSlot` do promoservice é dono do preview
  e da confirmação de exclusão; a feature só fornece o documento e as ações de rede.
- **Título capturado** (balizap `DocumentDropzone captureTitle=true`): após escolher o arquivo, um
  input inline pede o título (default = nome do arquivo sem extensão) antes de submeter. Também aceita
  **link externo** (URL) como alternativa ao arquivo. Não faz parte do kit base do promoservice.

```tsx
// Slot de título fixo — não pergunta título (promoservice)
<DocumentSlot title="Orçamento assinado" document={signedDoc}
  uploading={upload.isPending} progress={upload.progress}
  deleting={remove.isPending} readOnly={!can(P.UPDATE)}
  onUpload={(file) => upload.mutate(file)} onDelete={() => remove.mutate()} onError={toast.error} />

// Anexo solto — o dropzone só valida e devolve o arquivo
<DocumentDropzone uploading={upload.isPending} progress={upload.progress}
  onSelect={(file) => upload.mutate(file)} onError={toast.error} />
```

## Validação — `useFileUpload` (validator-only, NUNCA mutation)

Hook puro, vendorável verbatim. Retorna union discriminada pronta pra `toast.error`. **`validate` nunca
envia nada** — a mutation é custom por feature (ver `uploads.md` Don'ts) e, para ter progresso, passa
pelo `useUploadMutation` (próxima seção, no MESMO arquivo `hooks/useFileUpload.ts`).

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

## Progresso de envio — `ApiClient.upload` + `useUploadMutation` + `UploadProgress` (2026-10-01)

Todo upload com espera visível (foto, vídeo, documento, logo) mostra uma **barra de progresso real**.
`fetch` não tem evento de progresso de upload — o transporte é **`XMLHttpRequest`** com
`xhr.upload.onprogress`, encapsulado em `ApiClient.upload` (promoservice `lib/api/client.ts`):

```ts
client.upload<T>(url, form: FormData, { method?: "POST" | "PUT", onProgress?: (percent: number) => void }): Promise<ApiResponse<T>>
// PUT = rotas "substituir a instância única" (logo/banner); padrão POST
```

- Mesmo contrato do `request()`: Bearer em memória; **um** refresh-and-retry em 401 pelo lock
  compartilhado (o body é reenviado e o progresso recomeça em 0); resposta camelCased; falha de
  transporte vira `TypeError` → `NETWORK_ERROR` (status 0), **nunca** encerra sessão; sem
  `Content-Type` manual (o browser gera o boundary do multipart).
- `onProgress` recebe inteiro 0–100 dos bytes do **body enviados** (só repassa mudança de %).
  **100 = "os bytes saíram", não "o servidor terminou"** — o backend ainda valida/converte (AVIF,
  thumbnail). Por isso a UI troca para "Processando…" (indeterminado, barra pulsando) aos 100%.

```ts
// hooks/useFileUpload.ts — envelope de useMutation que carrega o estado de progresso
const uploadLogo = useUploadMutation({
  mutationFn: async (file: File, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return (await client.upload<OrgBranding>(`${base}/logo`, form, { onProgress })).data;
  },
  onSuccess: invalidate,
  onError: (error) => toast.error(UploadError.fromUnknown(error).message),
});
// retorno = UseMutationResult + { progress: number | null }  (null ocioso · 0 ao iniciar, inclui a
// redução no browser · 0–100 · volta a null no settled)

<ImageDropzone busy={uploadLogo.isPending} progress={uploadLogo.progress} … />
```

- Componentes apresentacionais (`ImageDropzone`, `DocumentDropzone`, `DocumentSlot`, `PhotoGallery`)
  ganham `progress?: number | null` e desenham `<UploadProgress value={progress} />`
  (`components/uploads/UploadProgress.tsx`: `Progress` shadcn + rótulo `Enviando... 42%` →
  `Processando...`; `role="status"`, `aria-live="polite"`; é `span`-wrapper para morar dentro de
  `<button>`). Sem `progress`, cai no spinner "Enviando…" (compatível com mutation comum).
- Quem faz `FormData` e chama `client.upload` é a **feature**; o dropzone só valida e devolve o
  arquivo. `useFileUpload` continua **validator-only**.
- Backend multipart sem mudança. Upload que NÃO é multipart (PUT presigned direto ao storage) usa o
  mesmo XHR com `upload.onprogress` — a regra é "progresso real via XHR", nunca barra falsa por timer.

## Redução no navegador — `compressImage(s)` (`lib/utils/image-compress.ts`)

Foto de celular moderno passa de 10 MB (limite de entrada do backend) e o backend a reduz para 1920px
em AVIF de qualquer jeito — subir o original gasta franquia de dados e dá 400. Antes do `FormData`:

```ts
const payload = await compressImages(files); // dentro do mutationFn → a barra já mostra 0% durante a redução
```

- Só reduz imagem > 1 MB; **GIF, SVG e AVIF passam intactos**; maior lado 1920, JPEG 0.85, fundo
  branco (PNG com alfa não vira preto), EXIF **aplicado** no decode (`imageOrientation: "from-image"`:
  o backend não aplica). Falha na redução devolve o arquivo original — o servidor segue validando.
- O **teto do dropzone é o do arquivo ORIGINAL** (`MAX_SOURCE_BYTES` = 40 MB, o que o browser
  decodifica sem travar a aba), **não** o do servidor — senão a foto de 12 MB é barrada aqui sem
  motivo, ou passa e morre num 400.

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

Na mutation: `mutationFn` faz `FormData` (`file`, `title?`, `aliases?`, `category?`) e chama
`client.upload`; o `onError` converte com `UploadError.fromUnknown(error)` (o `ApiError` já traz
`status`; falha de rede = status 0 → "network") e chama `toast.error(err.message)`.

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
· **Excluir** (`Trash2`, `variant="destructive"` → abre `ConfirmDialog`). "Copiar link" só existe
onde há URL pública (balizap); o `DocumentSlot`/`ImageDropzone` do promoservice têm Visualizar ·
Baixar · Substituir · Excluir. Ícone de ação inline: o set do projeto (`react-icons/lu` nos apps
novos — promoservice/kailos; `lucide-react` onde ainda é o idiom shadcn do arquivo); ícone de
identidade de arquivo = `react-icons/fa6` (`file-types`).

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

## Anexar pelo menu — `preventDefault()` no `onSelect` prende a página

`DropdownMenuItem` que abre `<input type="file">` **NÃO** chama `event.preventDefault()`. No Radix,
prevenir o select mantém o menu ABERTO, e `DropdownMenu` é modal por default: o resto da página fica
com `pointer-events: none` e o foco preso no content. O usuário escolhe o arquivo, o chip aparece —
e o clique/tecla seguinte só serve para fechar o menu. O sintoma NUNCA aparece como "menu preso";
aparece como **"o botão de enviar não funciona só com anexo"** e **"tenho que clicar no campo pra
digitar"** — os dois foram reportados como bug de composer.

```tsx
// ERRADO — menu fica aberto, modal, com o foco preso
onSelect={(event) => {
  event.preventDefault();
  attachments.openFileDialog();
}}
// CERTO — item de menu fecha (é o comportamento normal); o input.click() roda dentro do gesto
onSelect={() => attachments.openFileDialog()}
```

**Depois que o anexo entra, o caret vai para o campo de texto.** Anexar é o começo da mensagem, não
o fim. Só no CRESCIMENTO da lista (remover anexo não rouba foco; arquivo recusado pela validação
abre dialog de erro, que ficaria com o foco roubado), e dentro de `requestAnimationFrame` — o
`FocusScope` do Radix devolve o foco ao trigger do menu num `setTimeout(0)` ao fechar, então sem o
rAF o restore chega depois e vence:

```tsx
const attachmentCountRef = useRef(files.length);
useEffect(() => {
  const grew = files.length > attachmentCountRef.current;
  attachmentCountRef.current = files.length;
  if (!grew) {
    return;
  }
  const frame = requestAnimationFrame(() => {
    formRef.current?.querySelector<HTMLTextAreaElement>('textarea[name="message"]')?.focus();
  });
  return () => cancelAnimationFrame(frame);
}, [files.length]);
```

**Anexo sem texto é mensagem válida** (chat com IA): system prompt + documento já bastam para
começar. O gate de envio é `hasText || hasAttachments` — nunca só texto, e o botão de enviar nunca
é desabilitado por campo vazio quando há anexo.

## Variante — arquivos pendentes dentro de um form de CRIAÇÃO (nexarena)

Caso real: o usuário monta o evento e anexa documentos/banners **antes** do registro existir (sem
`eventId`, não há endpoint para receber o arquivo). Esta variante **não muda** (decisão 2026-10-01;
só ganha a barra de progresso) e é a referência para qualquer form de criação com anexos:
nexarena `components/events/form-sections/DocumentsSection.tsx` e `MediaSection.tsx`
(`components/organizations/OrgMediaSection.tsx` segue o mesmo desenho com `onPendingLogo/Banner/Gallery`).

- A seção é uma **tab/bloco do form** que edita uma lista no state do form (`value: JsonList` /
  `onChange`) e recebe `organizationId` + `eventId?` opcionais.
- **Sem `eventId` (criação):** o arquivo escolhido vira item **pendente** em state local
  (`{ file: File, title }`) — prévia por `URL.createObjectURL`, **revogada** no cleanup do effect e
  quando o item sai. Nada vai à rede; o pendente é listado junto dos salvos, marcado como pendente.
- **Com `eventId` (edição ou depois do 1º save):** o mesmo gesto envia na hora (`toast.promise`:
  "Enviando <título>…" → sucesso/erro), o resultado entra no `value` do form e o pendente sai.
- **Presets de título** (Regulamento, Termos, Termo de Responsabilidade…) aparecem como slots
  vazios; documento livre pede título. Substituição de um salvo = item `replacement` até confirmar.
- Remoção distingue os três tipos (salvo → `deleteDocument` no servidor; pendente/replacement →
  só descarta do state) e confirma sempre por `ConfirmDialog`.
- Validação de tamanho/tipo no `useFileUpload` antes de aceitar o arquivo no estado pendente (falha
  rápido, mesmo sem rede).
- Quando o envio ocorre (por arquivo), usar `useUploadMutation` para ter `progress` — nexarena ganha
  só isto nesta rodada.

Use esta variante **apenas** quando a entidade pode não existir ainda. Se o form já edita um registro
salvo, o fluxo normal (dropzone → upload imediato) é o certo.

## Don'ts

- **NUNCA** mutation dentro do `useFileUpload` — é validator-only; mutation é custom por feature e,
  com progresso, passa por `useUploadMutation` + `client.upload` (XHR).
- **NUNCA** barra de progresso falsa (timer/`setInterval`) nem `fetch` quando há progresso a mostrar.
- **NUNCA** deixar a barra parada em 100% — aos 100 vira "Processando…".
- **NUNCA** teto do dropzone de foto igual ao do servidor quando há `compressImage` (é o do original).
- **NUNCA** confirmar delete com tira inline/accordion/button-swap — é `ConfirmDialog` (ref `overlays.md`).
- **NUNCA** botão three-dots solto pra ações — o card/asset cheio JÁ é o trigger do menu.
- **NUNCA** inferir extensão/ícone na mão — use `fileTypeMeta` (e no backend `ext_from_name`).
- **NUNCA** `<img src>` direto pra arquivo de `visibility != "public"` — resolva via endpoint (presigned).
- **NUNCA** montar URL de upload na mão — `uploadsUrl`/`getFileApiUrl`/`getPhotoDisplayUrl`.
- **NUNCA** acoplar fetch/mutation no componente apresentacional — ele recebe callbacks; dados ficam no hook do projeto.
- **NUNCA** `accept`/whitelist divergente do backend — `DOC_ACCEPT_ATTR` espelha `ALLOWED_DOC_EXTS`.
- **NUNCA** `event.preventDefault()` no `onSelect` do item que abre o file picker — prende o menu modal sobre a página (foco + `pointer-events`).
- **NUNCA** exigir texto para enviar mensagem com anexo, nem deixar o foco fora do campo depois de anexar.
