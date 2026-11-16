/**
 * Canonical (byte-identical across apps, no app imports): chunked upload against a fake
 * transport that mimics the `/upload-sessions` contract.
 */
import { describe, expect, it } from "vitest";
import {
  ChunkUploadError,
  stageLargeFormFile,
  uploadFileInChunks,
  type ChunkTransport,
} from "../chunked-upload";
import { CHUNK_BYTES } from "../upload-limits";

const MIB = 1024 * 1024;

function fakeFile(size: number): File {
  return new File([new Uint8Array(size)], "video.mp4", { type: "video/mp4" });
}

interface FakeOptions {
  /** Scripted behaviours consumed per PUT, in order; default = success. */
  puts?: Array<"ok" | "network" | "network-after-write" | "conflict" | "server-error">;
}

function makeTransport(options: FakeOptions = {}) {
  const script = [...(options.puts ?? [])];
  const state = { offset: 0, puts: [] as number[], gets: 0 };
  const transport: ChunkTransport = {
    async json(method) {
      if (method === "POST") {
        return { status: 201, body: { id: "s1", chunk_bytes: CHUNK_BYTES, offset: 0 } };
      }
      if (method === "GET") {
        state.gets += 1;
        return { status: 200, body: { id: "s1", offset: state.offset, state: "uploading" } };
      }
      return { status: 204, body: null };
    },
    async putChunk(path, chunk, onBytes) {
      const requested = Number(new URL(`http://x${path}`).searchParams.get("offset"));
      const step = script.shift() ?? "ok";
      state.puts.push(requested);
      if (step === "network") throw new TypeError("offline");
      if (step === "server-error") return { status: 503, body: { detail: "busy" } };
      if (step === "conflict") {
        return { status: 409, body: { detail: "out of sync", offset: state.offset } };
      }
      onBytes?.(chunk.size / 2);
      if (requested !== state.offset) {
        return { status: 409, body: { detail: "out of sync", offset: state.offset } };
      }
      state.offset += chunk.size;
      if (step === "network-after-write") throw new TypeError("lost response");
      onBytes?.(chunk.size);
      return { status: 200, body: { offset: state.offset } };
    },
  };
  return { transport, state };
}

describe("uploadFileInChunks", () => {
  it("splits a 20 MiB file into 3 chunks with monotonic progress", async () => {
    const { transport, state } = makeTransport();
    const seen: number[] = [];
    const id = await uploadFileInChunks(fakeFile(20 * MIB), transport, {
      backoffMs: 0,
      onProgress: (sent, total) => {
        expect(total).toBe(20 * MIB);
        seen.push(sent);
      },
    });
    expect(id).toBe("s1");
    expect(state.puts).toEqual([0, 8 * MIB, 16 * MIB]);
    expect([...seen].sort((a, b) => a - b)).toEqual(seen);
    expect(seen.at(-1)).toBe(20 * MIB);
  });

  it("resyncs to the server offset on 409", async () => {
    const { transport, state } = makeTransport({ puts: ["conflict"] });
    await uploadFileInChunks(fakeFile(10 * MIB), transport, { backoffMs: 0 });
    expect(state.offset).toBe(10 * MIB);
    expect(state.puts.slice(0, 2)).toEqual([0, 0]);
  });

  it("retries after a network error and resumes from the GET offset (no double write)", async () => {
    const { transport, state } = makeTransport({ puts: ["network-after-write"] });
    await uploadFileInChunks(fakeFile(10 * MIB), transport, { backoffMs: 0 });
    expect(state.gets).toBe(1);
    // chunk 0 landed before the response was lost: next PUT starts at 8 MiB, not 0.
    expect(state.puts).toEqual([0, 8 * MIB]);
    expect(state.offset).toBe(10 * MIB);
  });

  it("gives up after 3 retries and throws fatal 4xx as ChunkUploadError", async () => {
    const failing = makeTransport({ puts: ["network", "network", "network", "network"] });
    await expect(
      uploadFileInChunks(fakeFile(10 * MIB), failing.transport, { backoffMs: 0 })
    ).rejects.toBeInstanceOf(TypeError);

    const { transport } = makeTransport();
    const fatal: ChunkTransport = {
      ...transport,
      putChunk: async () => ({ status: 400, body: { detail: "arquivo inválido" } }),
    };
    await expect(
      uploadFileInChunks(fakeFile(10 * MIB), fatal, { backoffMs: 0 })
    ).rejects.toMatchObject({ status: 400, message: "arquivo inválido" });
  });

  it("surfaces 413 from session creation", async () => {
    const { transport } = makeTransport();
    const tooBig: ChunkTransport = {
      ...transport,
      json: async () => ({ status: 413, body: { detail: "grande demais" } }),
    };
    const error = await uploadFileInChunks(fakeFile(10 * MIB), tooBig).catch((e) => e);
    expect(error).toBeInstanceOf(ChunkUploadError);
    expect(error.status).toBe(413);
  });
});

describe("stageLargeFormFile", () => {
  it("leaves a small file's form untouched", async () => {
    const { transport, state } = makeTransport();
    const form = new FormData();
    form.append("file", fakeFile(1 * MIB));
    expect(await stageLargeFormFile(form, transport)).toBe(form);
    expect(state.puts).toEqual([]);
  });

  it("swaps file for file_upload_id and keeps the other fields in order", async () => {
    const { transport } = makeTransport();
    const form = new FormData();
    form.append("kind", "video");
    form.append("file", fakeFile(9 * MIB));
    form.append("client_id", "c1");
    const staged = await stageLargeFormFile(form, transport, { backoffMs: 0 });
    expect(staged).not.toBe(form);
    expect([...staged.keys()]).toEqual(["kind", "file_upload_id", "client_id"]);
    expect(staged.get("file_upload_id")).toBe("s1");
    expect(staged.get("client_id")).toBe("c1");
  });
});
