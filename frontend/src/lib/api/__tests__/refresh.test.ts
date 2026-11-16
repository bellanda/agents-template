import { setAccessToken } from "@/lib/api/access-token-store";
import { apiFetch, registerSessionRefresher } from "@/lib/api/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const fetchMock = vi.fn<typeof fetch>();

function authorizationOf(callIndex: number): string | null {
  const init = fetchMock.mock.calls[callIndex][1] as RequestInit;
  return new Headers(init.headers).get("Authorization");
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  setAccessToken(null);
  registerSessionRefresher(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// Regression (audit 2026-11-13 template-gap-03): raw fetch never attached the Bearer nor renewed
// the session on 401.
describe("apiFetch", () => {
  it("sends the session token as Bearer, falling back to the userId stub", async () => {
    fetchMock.mockResolvedValue(json(200));

    await apiFetch("/api/v1/agents/threads", {}, { userId: "default_user" });
    expect(authorizationOf(0)).toBe("Bearer default_user");

    setAccessToken("real-token");
    await apiFetch("/api/v1/agents/threads", {}, { userId: "default_user" });
    expect(authorizationOf(1)).toBe("Bearer real-token");
  });

  it("renews the session once on 401 and retries with the new token", async () => {
    setAccessToken("expired");
    registerSessionRefresher(async () => {
      setAccessToken("renewed");
      return true;
    });
    fetchMock.mockResolvedValueOnce(json(401)).mockResolvedValueOnce(json(200, { ok: true }));

    const response = await apiFetch("/api/v1/agents/threads");

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(authorizationOf(0)).toBe("Bearer expired");
    expect(authorizationOf(1)).toBe("Bearer renewed");
  });

  it("shares ONE refresh between concurrent 401s", async () => {
    setAccessToken("expired");
    const refresher = vi.fn(async () => {
      await Promise.resolve();
      setAccessToken("renewed");
      return true;
    });
    registerSessionRefresher(refresher);
    fetchMock.mockImplementation(async (_url, init) =>
      new Headers((init as RequestInit).headers).get("Authorization") === "Bearer renewed"
        ? json(200)
        : json(401)
    );

    const responses = await Promise.all([apiFetch("/a"), apiFetch("/b"), apiFetch("/c")]);

    expect(responses.map((r) => r.status)).toEqual([200, 200, 200]);
    expect(refresher).toHaveBeenCalledTimes(1);
  });

  it("returns the 401 when the refresh is refused, without retrying", async () => {
    setAccessToken("expired");
    registerSessionRefresher(async () => false);
    fetchMock.mockResolvedValue(json(401));

    const response = await apiFetch("/api/v1/agents/threads");

    expect(response.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not refresh on 5xx or when no refresher is registered", async () => {
    const refresher = vi.fn(async () => true);
    registerSessionRefresher(refresher);
    fetchMock.mockResolvedValue(json(503));
    expect((await apiFetch("/x")).status).toBe(503);
    expect(refresher).not.toHaveBeenCalled();

    registerSessionRefresher(null);
    fetchMock.mockResolvedValue(json(401));
    expect((await apiFetch("/x")).status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
