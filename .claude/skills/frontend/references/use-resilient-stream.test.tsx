// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { StreamOpenArgs } from "../resilient-stream";
import { useResilientStream } from "../use-resilient-stream";

/**
 * audit 2026-11-15 r2-kailos-fe-hooks-lib-01: a token rotation restarts the loop; the new loop
 * must resync on its first open (a reconnect), the very first connection must not.
 */
let opens: StreamOpenArgs[];
const open = (args: StreamOpenArgs) =>
  new Promise<void>(() => {
    opens.push(args);
  });

type Props = { token: string | null; key: string; enabled: boolean };

function mount(onResync: () => void, initial: Props) {
  return renderHook(
    (p: Props) =>
      useResilientStream({
        accessToken: p.token,
        streamKey: p.key,
        enabled: p.enabled,
        open,
        getAccessToken: () => p.token,
        onResync,
      }),
    { initialProps: initial }
  );
}

describe("useResilientStream", () => {
  beforeEach(() => {
    opens = [];
  });
  afterEach(() => vi.restoreAllMocks());

  it("resyncs when a token rotation reopens the stream, not on the first connection", async () => {
    const onResync = vi.fn();
    const { rerender } = mount(onResync, { token: "A", key: "org-1", enabled: true });
    await act(async () => {});
    expect(opens).toHaveLength(1);
    opens[0].onOpen();
    expect(onResync).not.toHaveBeenCalled();

    rerender({ token: "B", key: "org-1", enabled: true });
    await act(async () => {});
    expect(opens).toHaveLength(2);
    opens[1].onOpen();
    expect(onResync).toHaveBeenCalledTimes(1);
  });

  it("treats a new streamKey or a disable/enable as a fresh stream (no resync)", async () => {
    const onResync = vi.fn();
    const { rerender } = mount(onResync, { token: "A", key: "org-1", enabled: true });
    await act(async () => {});
    opens[0].onOpen();

    rerender({ token: "A", key: "org-2", enabled: true });
    await act(async () => {});
    opens[1].onOpen();
    rerender({ token: "A", key: "org-2", enabled: false });
    rerender({ token: "A", key: "org-2", enabled: true });
    await act(async () => {});
    opens[2].onOpen();
    expect(onResync).not.toHaveBeenCalled();
  });
});
