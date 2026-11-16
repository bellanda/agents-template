/**
 * Chunked upload client (decision 2026-11-16). Canonical copy: byte-identical in every app,
 * no app imports — `client.ts` differs per app, so it passes a `ChunkTransport` instead.
 * Source: `/mnt/c/Users/gusta/OneDrive/Config Files/agents/skills/frontend/references/`
 * (shared-widgets manifest).
 *
 * Why: nginx caps a request body at 20 MB and Cloudflare at 100 MB / ~100 s, so a 38 MB iPhone
 * video sent as ONE multipart request got 413 (prod 2026-11-16). Every request stays <= 20 MB;
 * any file above `CHUNK_BYTES` goes to an upload session in sequential chunks and the domain
 * endpoint then receives `file_upload_id` instead of the `file` field.
 *
 * Backend contract (base `/api/v1` belongs to the transport):
 *   POST   /upload-sessions {filename, mime_type, size_bytes} -> 201 {id, chunk_bytes, offset, expires_at}
 *   PUT    /upload-sessions/{id}?offset=N  (octet-stream, <= chunk_bytes) -> 200 {offset}
 *          409 {detail, offset} = out of sync: continue from the server offset; other 4xx fatal
 *   GET    /upload-sessions/{id} -> {id, offset, size_bytes, state, error}
 *   DELETE /upload-sessions/{id} -> 204
 */
import { CHUNK_BYTES } from "./upload-limits";

/** One HTTP verdict. Transports resolve for ANY status (so 409 bodies stay readable) and only
 * REJECT when no verdict arrived (offline, DNS, CORS, abort) — the caller treats a rejection as
 * a network failure. `body` is the parsed JSON (snake_case, untouched) or text. */
export interface ChunkTransportResponse {
  status: number;
  body: unknown;
}

export interface ChunkTransport {
  /** JSON request. Handles auth/refresh itself; `path` is relative to the API base. */
  json(
    method: "POST" | "GET" | "DELETE",
    path: string,
    body?: unknown
  ): Promise<ChunkTransportResponse>;
  /** Raw `application/octet-stream` PUT of one chunk; `onBytes` reports bytes of THIS chunk sent. */
  putChunk(
    path: string,
    chunk: Blob,
    onBytes?: (sentBytes: number) => void
  ): Promise<ChunkTransportResponse>;
}

export interface ChunkedUploadOptions {
  onProgress?: (sentBytes: number, totalBytes: number) => void;
  signal?: AbortSignal;
  /** Base of the exponential retry backoff in ms (tests pass 0). Default 500. */
  backoffMs?: number;
}

/** Non-retryable server verdict (413 too big, 429 too many sessions, 400 fatal...). */
export class ChunkUploadError extends Error {
  readonly status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ChunkUploadError";
    this.status = status;
  }
}

const MAX_RETRIES = 3;
const MAX_RESYNCS = 20;
const DEFAULT_BACKOFF_MS = 500;
const SESSIONS_PATH = "/upload-sessions";

interface SessionInfo {
  id: string;
  chunk_bytes?: number;
  offset?: number;
}

function detailOf(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function offsetOf(body: unknown): number | null {
  if (body && typeof body === "object" && "offset" in body) {
    const value = Number((body as { offset: unknown }).offset);
    if (Number.isFinite(value) && value >= 0) return value;
  }
  return null;
}

const isOk = (status: number) => status >= 200 && status < 300;

function sleep(ms: number): Promise<void> {
  return ms > 0 ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve();
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("Upload cancelado", "AbortError");
}

async function createSession(file: File | Blob, transport: ChunkTransport): Promise<SessionInfo> {
  const res = await transport.json("POST", SESSIONS_PATH, {
    filename: file instanceof File ? file.name : "upload",
    mime_type: file.type || "application/octet-stream",
    size_bytes: file.size,
  });
  if (!isOk(res.status)) {
    throw new ChunkUploadError(res.status, detailOf(res.body, "Não foi possível iniciar o envio."));
  }
  return res.body as SessionInfo;
}

/**
 * Uploads `file` to a new session in sequential chunks and resolves with the upload id.
 * Each chunk is retried up to 3x with exponential backoff on network failure / 5xx (after a
 * network failure the server offset is re-read with GET before continuing); 409 resyncs to
 * the offset the server reports; any other 4xx throws `ChunkUploadError`. Progress is
 * monotonic over the whole file.
 */
export async function uploadFileInChunks(
  file: File | Blob,
  transport: ChunkTransport,
  options: ChunkedUploadOptions = {}
): Promise<string> {
  const { onProgress, signal, backoffMs = DEFAULT_BACKOFF_MS } = options;
  const total = file.size;
  let reported = 0;
  const report = (sent: number) => {
    const clamped = Math.min(total, Math.max(reported, sent));
    if (clamped === reported && reported !== 0) return;
    reported = clamped;
    onProgress?.(reported, total);
  };

  throwIfAborted(signal);
  const session = await createSession(file, transport);
  const chunkBytes =
    session.chunk_bytes && session.chunk_bytes > 0 ? session.chunk_bytes : CHUNK_BYTES;
  const path = `${SESSIONS_PATH}/${session.id}`;
  let offset = session.offset ?? 0;
  let resyncs = 0;
  let failures = 0;
  report(offset);

  while (offset < total) {
    throwIfAborted(signal);
    const end = Math.min(offset + chunkBytes, total);
    const base = offset;
    try {
      const res = await transport.putChunk(
        `${path}?offset=${base}`,
        file.slice(base, end),
        (sent) => report(base + sent)
      );
      if (isOk(res.status)) {
        offset = offsetOf(res.body) ?? end;
        failures = 0;
        report(offset);
        continue;
      }
      if (res.status === 409) {
        const serverOffset = offsetOf(res.body);
        resyncs += 1;
        if (serverOffset === null || resyncs > MAX_RESYNCS) {
          throw new ChunkUploadError(409, detailOf(res.body, "Envio fora de sincronia."));
        }
        offset = serverOffset;
        continue;
      }
      if (res.status < 500) {
        throw new ChunkUploadError(res.status, detailOf(res.body, "Falha no envio do arquivo."));
      }
      failures += 1;
      if (failures > MAX_RETRIES) {
        throw new ChunkUploadError(res.status, detailOf(res.body, "Erro no servidor ao enviar."));
      }
      await sleep(backoffMs * 2 ** (failures - 1));
    } catch (error) {
      if (error instanceof ChunkUploadError || signal?.aborted) throw error;
      // Network failure: no verdict arrived, so the chunk may or may not have landed.
      failures += 1;
      if (failures > MAX_RETRIES) throw error;
      await sleep(backoffMs * 2 ** (failures - 1));
      offset = await readServerOffset(path, transport, offset);
    }
  }
  return session.id;
}

/** Re-reads the session offset after a network failure; keeps `fallback` if GET also fails. */
async function readServerOffset(
  path: string,
  transport: ChunkTransport,
  fallback: number
): Promise<number> {
  try {
    const res = await transport.json("GET", path);
    if (isOk(res.status)) return offsetOf(res.body) ?? fallback;
  } catch {
    // Still offline: the next attempt will fail and count against the retry budget.
  }
  return fallback;
}

/**
 * If the form's `file` field is larger than `CHUNK_BYTES`, uploads it in chunks and returns a
 * NEW FormData where `file` became `file_upload_id` (every other entry kept, same order).
 * Otherwise returns the same form untouched.
 */
export async function stageLargeFormFile(
  form: FormData,
  transport: ChunkTransport,
  options: ChunkedUploadOptions = {}
): Promise<FormData> {
  const file = form.get("file");
  if (!(file instanceof Blob) || file.size <= CHUNK_BYTES) return form;
  const uploadId = await uploadFileInChunks(file, transport, options);
  const staged = new FormData();
  for (const [key, value] of form.entries()) {
    if (key === "file") staged.append("file_upload_id", uploadId);
    else staged.append(key, value);
  }
  return staged;
}
