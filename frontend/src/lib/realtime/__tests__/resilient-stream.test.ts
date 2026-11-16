// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  HIDDEN_REOPEN_AFTER_MS,
  STREAM_IDLE_TIMEOUT_MS,
  startResilientStream,
  type StreamOpenArgs,
} from "../resilient-stream";

/**
 * core-spa-06 (audit 2026-11-13): a half-open connection never fails, its read just never returns.
 * These tests use a transport whose promise only settles on abort (or never, for the worst case).
 */
interface Attempt {
  args: StreamOpenArgs;
  end: () => void;
}
let attempts: Attempt[];

function hangingOpen(args: StreamOpenArgs): Promise<void> {
  return new Promise<void>((resolve) => {
    attempts.push({ args, end: resolve });
    args.onOpen();
    // A signal-ignoring transport is the worst case; the loop must not depend on it.
  });
}

function setVisibility(state: "hidden" | "visible") {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}

function start(extra: Partial<Parameters<typeof startResilientStream>[0]> = {}) {
  const onResync = vi.fn();
  const stop = startResilientStream({
    open: hangingOpen,
    getAccessToken: () => "tok",
    fallbackAccessToken: "tok",
    onResync,
    random: () => 0,
    ...extra,
  });
  return { stop, onResync };
}

describe("startResilientStream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    attempts = [];
    setVisibility("visible");
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("reopens and resyncs when no byte arrives for 45 s (half-open connection)", async () => {
    const { stop, onResync } = start();
    await vi.advanceTimersByTimeAsync(0);
    expect(attempts).toHaveLength(1);
    expect(onResync).not.toHaveBeenCalled(); // first open: the queries just loaded

    await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS - 1);
    expect(attempts).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(attempts).toHaveLength(2);
    expect(attempts[0].args.signal.aborted).toBe(true);
    expect(onResync).toHaveBeenCalledTimes(1);
    stop();
  });

  it("heartbeats (onActivity) keep the connection alive", async () => {
    const { stop } = start();
    await vi.advanceTimersByTimeAsync(0);
    for (let i = 0; i < 5; i += 1) {
      await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS - 5_000);
      attempts[0].args.onActivity();
    }
    expect(attempts).toHaveLength(1);
    stop();
  });

  it("reopens on foreground after more than 30 s hidden, not after a short blip", async () => {
    const { stop, onResync } = start();
    await vi.advanceTimersByTimeAsync(0);

    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(HIDDEN_REOPEN_AFTER_MS - 1_000);
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    expect(attempts).toHaveLength(1);
    attempts[0].args.onActivity();

    setVisibility("hidden");
    await vi.advanceTimersByTimeAsync(40_000);
    attempts[0].args.onActivity(); // heartbeat: keeps the watchdog out of this test
    await vi.advanceTimersByTimeAsync(20_000);
    setVisibility("visible");
    await vi.advanceTimersByTimeAsync(0);
    expect(attempts).toHaveLength(2);
    expect(onResync).toHaveBeenCalledTimes(1);
    stop();
  });

  it("resyncs on every reopen, including when the first attempt failed before opening", async () => {
    let calls = 0;
    const onResync = vi.fn();
    const stop = startResilientStream({
      open: async (args) => {
        calls += 1;
        if (calls === 1) {
          args.onError(Object.assign(new Error("down"), { status: 503 }));
          return;
        }
        args.onOpen();
        await new Promise(() => {});
      },
      getAccessToken: () => "tok",
      fallbackAccessToken: "tok",
      onResync,
      random: () => 0,
    });
    await vi.advanceTimersByTimeAsync(2_000);
    expect(calls).toBe(2);
    expect(onResync).toHaveBeenCalledTimes(1);
    stop();
  });

  it("refreshes the token on 401 and stops when the refresh itself is refused", async () => {
    const refreshToken = vi
      .fn()
      .mockRejectedValue(Object.assign(new Error("dead"), { status: 401 }));
    let calls = 0;
    const stop = startResilientStream({
      open: async (args) => {
        calls += 1;
        args.onError(Object.assign(new Error("expired"), { status: 401 }));
      },
      getAccessToken: () => "tok",
      fallbackAccessToken: "tok",
      refreshToken,
      random: () => 0,
    });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(refreshToken).toHaveBeenCalledTimes(1);
    expect(calls).toBe(1);
    stop();
  });

  it("stops for good on a stopOnStatuses status (403 without permission)", async () => {
    let calls = 0;
    const stop = startResilientStream({
      open: async (args) => {
        calls += 1;
        args.onError(Object.assign(new Error("forbidden"), { status: 403 }));
      },
      getAccessToken: () => "tok",
      fallbackAccessToken: "tok",
      refreshOnStatuses: [401],
      stopOnStatuses: [403],
    });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(calls).toBe(1);
    stop();
  });

  it("ignores callbacks of an attempt that was already replaced (signal-ignoring transport)", async () => {
    const { stop, onResync } = start();
    await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS);
    expect(attempts).toHaveLength(2);
    expect(onResync).toHaveBeenCalledTimes(1);
    // The stale first attempt wakes up: it must not resync again nor arm a watchdog.
    attempts[0].args.onOpen();
    attempts[0].args.onActivity();
    attempts[1].args.onActivity();
    await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS - 1);
    expect(attempts).toHaveLength(2);
    expect(onResync).toHaveBeenCalledTimes(1);
    stop();
  });

  it("stop() aborts the live attempt and never reopens", async () => {
    const { stop } = start();
    await vi.advanceTimersByTimeAsync(0);
    stop();
    expect(attempts[0].args.signal.aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(STREAM_IDLE_TIMEOUT_MS * 3);
    expect(attempts).toHaveLength(1);
  });
});
