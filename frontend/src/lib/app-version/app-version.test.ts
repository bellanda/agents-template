// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { describe, expect, it, vi } from "vitest";
import {
  claimPreloadReload,
  createPreloadErrorHandler,
  decideUpdateAction,
  fetchDeployedBuildId,
  hasReloadedFor,
  isChunkLoadError,
  isCountdownPaused,
  markReloadedFor,
  type UpdateState,
} from "./app-version";

const base: UpdateState = {
  updatePending: true,
  isHidden: false,
  isNavigating: false,
  reloadBlocked: false,
};

function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
  };
}

describe("decideUpdateAction", () => {
  it.each([
    [{ updatePending: false }, "wait"],
    [{ isHidden: true }, "reload-now"],
    [{ isNavigating: true }, "reload-on-navigation"],
    [{}, "countdown"],
    [{ reloadBlocked: true, isHidden: true }, "banner-only"],
  ] as const)("%o -> %s", (patch, expected) => {
    expect(decideUpdateAction({ ...base, ...patch })).toBe(expected);
  });
});

describe("fetchDeployedBuildId", () => {
  it("returns the id and null on any failure", async () => {
    const ok = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ buildId: "b2" }) });
    expect(await fetchDeployedBuildId(ok)).toBe("b2");
    expect(ok).toHaveBeenCalledWith("/version.json", { cache: "no-store" });
    const notFound = vi.fn().mockResolvedValue({ ok: false });
    expect(await fetchDeployedBuildId(notFound)).toBeNull();
    const html = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    expect(await fetchDeployedBuildId(html)).toBeNull();
    expect(await fetchDeployedBuildId(vi.fn().mockRejectedValue(new Error("offline")))).toBeNull();
  });
});

describe("anti-loop", () => {
  it("remembers the build we already reloaded for", () => {
    const storage = memoryStorage();
    expect(hasReloadedFor("b2", storage)).toBe(false);
    markReloadedFor("b2", storage);
    expect(hasReloadedFor("b2", storage)).toBe(true);
    expect(hasReloadedFor("b3", storage)).toBe(false);
  });

  it("fails closed when storage throws", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
    };
    expect(hasReloadedFor("b2", broken)).toBe(true);
  });

  it("claims a preload reload once per cooldown window", () => {
    const storage = memoryStorage();
    expect(claimPreloadReload(1_000_000, storage)).toBe(true);
    expect(claimPreloadReload(1_030_000, storage)).toBe(false);
    expect(claimPreloadReload(1_061_000, storage)).toBe(true);
  });
});

describe("preload error handling", () => {
  it("prevents default and reloads once per cooldown (real sessionStorage)", () => {
    sessionStorage.clear();
    const reload = vi.fn();
    const preventDefault = vi.fn();
    const handler = createPreloadErrorHandler(reload, () => 5_000_000);
    handler({ preventDefault });
    handler({ preventDefault });
    expect(preventDefault).toHaveBeenCalledTimes(2);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("recognises chunk errors from the main browsers", () => {
    expect(isChunkLoadError(new Error("Failed to fetch dynamically imported module: /a.js"))).toBe(
      true
    );
    expect(isChunkLoadError(new Error("Importing a module script failed."))).toBe(true);
    expect(isChunkLoadError(new Error("Cannot read properties of undefined"))).toBe(false);
  });
});

describe("isCountdownPaused", () => {
  const doc = (tag: string | null, dialog: boolean) =>
    ({
      activeElement: tag ? { tagName: tag, isContentEditable: false } : null,
      querySelector: () => (dialog ? {} : null),
    }) as never;
  it("pauses on focused field or open dialog only", () => {
    expect(isCountdownPaused(doc("INPUT", false))).toBe(true);
    expect(isCountdownPaused(doc("BODY", true))).toBe(true);
    expect(isCountdownPaused(doc("BODY", false))).toBe(false);
  });
});
