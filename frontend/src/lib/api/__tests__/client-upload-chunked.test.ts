/** `ApiClient.upload`: files above 8 MiB are staged in chunks and swapped for `file_upload_id`. */
import { setAccessToken } from "@/lib/api/access-token-store";
import { fastApiAdapter } from "@/lib/api/adapters";
import { ApiClient } from "@/lib/api/api-client";
import { uploadFile, UploadError } from "@/lib/api";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const MIB = 1024 * 1024;

interface SentXhr {
  method: string;
  url: string;
  body: unknown;
}

let sent: SentXhr[] = [];
let serverOffset = 0;

class FakeXhr {
  upload: { onprogress: ((e: unknown) => void) | null } = { onprogress: null };
  status = 0;
  responseText = "";
  responseType = "";
  withCredentials = false;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  private method = "";
  private url = "";
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader() {}
  getResponseHeader(name: string) {
    return name.toLowerCase() === "content-type" ? "application/json" : null;
  }
  send(body: unknown) {
    sent.push({ method: this.method, url: this.url, body });
    if (this.url.includes("/upload-sessions/")) {
      serverOffset += (body as Blob).size;
      this.responseText = JSON.stringify({ offset: serverOffset });
    } else {
      this.responseText = JSON.stringify({ id: "m1" });
    }
    this.status = 200;
    queueMicrotask(() => this.onload?.());
  }
}

const fetchMock = vi.fn<typeof fetch>();
const adapter = { ...fastApiAdapter, baseURL: "/api/v1" };

beforeEach(() => {
  sent = [];
  serverOffset = 0;
  fetchMock.mockReset();
  setAccessToken("tok");
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
});

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

function formWith(size: number): FormData {
  const form = new FormData();
  form.append("kind", "document");
  form.append("file", new File([new Uint8Array(size)], "big.pdf", { type: "application/pdf" }));
  return form;
}

const sessionCreated = () =>
  new Response(JSON.stringify({ id: "s1", chunk_bytes: 8 * MIB, offset: 0 }), {
    status: 201,
    headers: { "content-type": "application/json" },
  });

describe("ApiClient.upload chunking", () => {
  it("swaps a >8 MiB file for file_upload_id after chunking it", async () => {
    fetchMock.mockResolvedValue(sessionCreated());
    const percents: number[] = [];
    await new ApiClient(adapter).upload("/things", formWith(10 * MIB), {
      onProgress: (p) => percents.push(p),
    });

    const chunks = sent.filter((r) => r.url.includes("/upload-sessions/s1?offset="));
    expect(chunks.map((c) => c.method)).toEqual(["PUT", "PUT"]);
    const body = sent.find((r) => r.url.endsWith("/things"))!.body as FormData;
    expect(body.get("file_upload_id")).toBe("s1");
    expect(body.has("file")).toBe(false);
    expect(body.get("kind")).toBe("document");
    expect(percents.at(-1)).toBe(100);
  });

  it("direct skips staging and sends the file in the one request", async () => {
    await new ApiClient(adapter).upload("/things", formWith(10 * MIB), { direct: true });
    expect(sent).toHaveLength(1);
    expect((sent[0].body as FormData).has("file")).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps 413 on session creation to a too_large UploadError (chat uploadFile)", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Arquivo grande demais" }), {
        status: 413,
        headers: { "content-type": "application/json" },
      })
    );
    const file = new File([new Uint8Array(10 * MIB)], "big.pdf", { type: "application/pdf" });
    const error = await uploadFile(file, undefined, "alice").catch((e) => e);
    expect(error).toBeInstanceOf(UploadError);
    expect(error.code).toBe("too_large");
  });
});
