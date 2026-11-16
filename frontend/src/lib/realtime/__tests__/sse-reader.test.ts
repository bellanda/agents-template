// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { describe, expect, it, vi } from "vitest";
import { readSseBody } from "../sse-reader";

function bodyOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

describe("readSseBody", () => {
  it("delivers data lines across chunk boundaries and counts heartbeats as activity", async () => {
    const onData = vi.fn();
    const onActivity = vi.fn();
    await readSseBody(
      bodyOf([": connected\n\n", 'data: {"a":', '1}\n\n: heartbeat\n\ndata: {"b":2}\n\n']),
      { onData, onActivity }
    );
    expect(onData.mock.calls.map(([payload]) => payload)).toEqual(['{"a":1}', '{"b":2}']);
    expect(onActivity).toHaveBeenCalledTimes(3);
  });
});
