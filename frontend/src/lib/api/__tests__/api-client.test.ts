import { setAccessToken } from "@/lib/api/access-token-store";
import { fastApiAdapter } from "@/lib/api/adapters";
import { ApiClient } from "@/lib/api/api-client";
import { registerSessionRefresher } from "@/lib/api/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const json = (status: number, body: unknown = {}, headers: Record<string, string> = {}) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });

const fetchMock = vi.fn<typeof fetch>();
const adapter = { ...fastApiAdapter, baseURL: "/api/v1" };
const authOf = (i: number) =>
  new Headers((fetchMock.mock.calls[i][1] as RequestInit).headers).get("Authorization");

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  setAccessToken(null);
  registerSessionRefresher(null);
});
afterEach(() => vi.unstubAllGlobals());

// template-gap-03: the full client (case transform, adapters, shared 401 refresh, upload progress).
describe("ApiClient", () => {
  it("snake_cases the request, camelCases the response and sends the Bearer", async () => {
    fetchMock.mockResolvedValue(json(200, { user_name: "ana", nested_list: [{ some_key: 1 }] }));
    setAccessToken("tok");

    const res = await new ApiClient(adapter).post("/things", { userName: "ana" });

    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({
      user_name: "ana",
    });
    expect(authOf(0)).toBe("Bearer tok");
    expect(res.data).toEqual({ userName: "ana", nestedList: [{ someKey: 1 }] });
  });

  it("falls back to the open-identity stub and getRaw keeps snake_case", async () => {
    fetchMock.mockResolvedValue(json(200, { some_key: 1 }));
    const client = new ApiClient(adapter, { fallbackToken: () => "default_user" });

    const res = await client.getRaw("/x", { params: { pageSize: 5, empty: "" } });

    expect(authOf(0)).toBe("Bearer default_user");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/x?page_size=5");
    expect(res.data).toEqual({ some_key: 1 });
  });

  it("shares ONE refresh with apiFetch callers and retries with the new token", async () => {
    setAccessToken("expired");
    const refresher = vi.fn(async () => {
      await Promise.resolve();
      setAccessToken("renewed");
      return true;
    });
    registerSessionRefresher(refresher);
    fetchMock.mockImplementation(async (_u, init) =>
      new Headers((init as RequestInit).headers).get("Authorization") === "Bearer renewed"
        ? json(200, { ok: true })
        : json(401)
    );
    const client = new ApiClient(adapter);

    const results = await Promise.all([client.get("/a"), client.get("/b"), client.get("/c")]);

    expect(results.map((r) => r.status)).toEqual([200, 200, 200]);
    expect(refresher).toHaveBeenCalledTimes(1);
  });

  it("throws an ApiError with request id on 4xx, and NETWORK_ERROR on transport failure", async () => {
    fetchMock.mockResolvedValueOnce(json(404, { detail: "nope" }, { "x-request-id": "rid-1" }));
    const client = new ApiClient(adapter);
    await expect(client.get("/x")).rejects.toMatchObject({
      status: 404,
      message: "nope",
      code: "NOT_FOUND",
      requestId: "rid-1",
    });

    fetchMock.mockRejectedValueOnce(new TypeError("Load failed"));
    await expect(client.get("/x")).rejects.toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });

  it("treats a 204 with a JSON content-type as success", async () => {
    fetchMock.mockResolvedValue(json(204));
    const res = await new ApiClient(adapter).delete("/x/1");
    expect(res.status).toBe(204);
    expect(res.data).toBeNull();
  });
});

class FakeXhr {
  static instances: FakeXhr[] = [];
  upload: { onprogress: ((e: unknown) => void) | null } = { onprogress: null };
  headers: Record<string, string> = {};
  status = 200;
  responseText = "";
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  withCredentials = false;
  responseType = "";
  method = "";
  constructor() {
    FakeXhr.instances.push(this);
  }
  open(method: string) {
    this.method = method;
  }
  setRequestHeader(k: string, v: string) {
    this.headers[k] = v;
  }
  getResponseHeader(name: string) {
    return name === "content-type" ? "application/json" : null;
  }
  send() {}
}

describe("ApiClient.upload", () => {
  beforeEach(() => {
    FakeXhr.instances = [];
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
  });

  it("reports real progress, resolves camelCased JSON, and retries once after a 401 refresh", async () => {
    setAccessToken("expired");
    registerSessionRefresher(async () => {
      setAccessToken("renewed");
      return true;
    });
    const progress: number[] = [];
    const promise = new ApiClient(adapter).upload("/uploads", new FormData(), {
      onProgress: (p) => progress.push(p),
    });

    await vi.waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    const first = FakeXhr.instances[0];
    expect(first.headers.Authorization).toBe("Bearer expired");
    first.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
    first.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 }); // deduped
    first.status = 401;
    first.onload?.();

    await vi.waitFor(() => expect(FakeXhr.instances).toHaveLength(2));
    const second = FakeXhr.instances[1];
    expect(second.headers.Authorization).toBe("Bearer renewed");
    second.status = 201;
    second.responseText = JSON.stringify({ file_url: "/u/1" });
    second.onload?.();

    const res = await promise;
    expect(res.data).toEqual({ fileUrl: "/u/1" });
    expect(progress).toEqual([50, 0]);
  });

  it("maps an XHR transport failure to NETWORK_ERROR", async () => {
    const promise = new ApiClient(adapter).upload("/uploads", new FormData());
    await vi.waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    FakeXhr.instances[0].onerror?.();
    await expect(promise).rejects.toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });
});
