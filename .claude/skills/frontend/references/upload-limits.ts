/**
 * Fleet-wide per-FILE upload limits (decision 2026-11-16). Canonical copy: byte-identical in
 * every app, no app imports. Source: `/mnt/c/Users/gusta/OneDrive/Config Files/agents/skills/frontend/references/`
 * (shared-widgets manifest). Mirror of the backend limits.
 *
 * Why these numbers: every HTTP request stays <= 20 MB (nginx `client_max_body_size`;
 * Cloudflare allows 100 MB / ~100 s). Anything above `CHUNK_BYTES` is sent in chunks through
 * `chunked-upload.ts`, so the per-file cap is independent of the per-request cap.
 */
const MIB = 1024 * 1024;

/** Images are decoded/converted in memory on the server, so they keep the low cap. */
export const IMAGE_MAX_BYTES = 20 * MIB;
/** Anything that is only stored (documents, video, audio, attachments). */
export const FILE_MAX_BYTES = 500 * MIB;
/** Files above this go through the upload-session endpoint in chunks of this size. */
export const CHUNK_BYTES = 8 * MIB;
/**
 * Cap for PUBLIC (unauthenticated) uploads that skip chunking (`client.upload(..., { direct: true })`):
 * the whole multipart body must fit the 20 MB request limit, with room for the other form fields.
 */
export const DIRECT_MAX_BYTES = 18 * MIB;
