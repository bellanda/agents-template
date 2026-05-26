import { useCallback } from "react";

export interface UseFileUploadOptions {
  /** Max file size in bytes. */
  maxBytes: number;
  /** Allowed MIME types (exact match). */
  allowedMime: readonly string[];
  /** Allowed extensions (with leading dot, lowercase). */
  allowedExt: readonly string[];
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

/**
 * Client-side upload validator. Returns a `ValidationResult` discriminated
 * union: `{ ok: true, file }` to pass to the upload mutation, or
 * `{ ok: false, error }` ready to feed `toast.error`.
 *
 * Validator-only by design — the mutation (POST FormData) is the caller's
 * responsibility (see `uploadFile` in `lib/api.ts`). Server-side validation
 * (size, MIME) still runs in the backend; this just fails fast in the browser
 * with a friendlier message.
 */
export function useFileUpload(options: UseFileUploadOptions) {
  const { maxBytes, allowedMime, allowedExt } = options;

  const validate = useCallback(
    (file: File): ValidationResult => {
      if (file.size > maxBytes) {
        return {
          ok: false,
          error: `Arquivo muito grande (${formatBytes(file.size)}). Máximo: ${formatBytes(maxBytes)}.`,
        };
      }
      const mime = (file.type || "").toLowerCase();
      if (allowedMime.length > 0 && !allowedMime.includes(mime)) {
        return {
          ok: false,
          error: `Tipo não suportado (${mime || "desconhecido"}). Permitido: ${allowedMime.join(", ")}.`,
        };
      }
      const ext = extOf(file.name);
      if (allowedExt.length > 0 && !allowedExt.includes(ext)) {
        return {
          ok: false,
          error: `Extensão não suportada (${ext || "desconhecida"}). Permitido: ${allowedExt.join(", ")}.`,
        };
      }
      return { ok: true, file };
    },
    [maxBytes, allowedMime, allowedExt]
  );

  return { validate };
}
