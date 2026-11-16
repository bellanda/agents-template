/**
 * React wrapper of `startResilientStream` (fleet standard, audit 2026-11-13 core-spa-06).
 *
 * The effect deps are `[enabled, accessToken, streamKey]` only. Everything else is read through a
 * ref, so inline closures (`open`, `onResync`) never tear the stream down — there is no replay,
 * and events in the reconnect window would be lost. The access token is REACTIVE (the caller
 * passes it from `useSyncExternalStore(subscribeAccessToken, getAccessToken)`): rotation here or
 * in another tab reopens with the new token, and a cold load where the token arrives after the
 * mount still connects.
 *
 * `streamKey` is whatever identifies the connection (usually the org id): changing it reopens.
 *
 * A restart caused by a token change is a RECONNECT, not a cold start: the hook remembers that a
 * previous loop already opened and the new loop resyncs on its first open (there is no replay;
 * an idle visible tab after a backend restart would otherwise never refetch what it missed).
 * Disabling the hook or changing `streamKey` forgets it: that is a different stream.
 */
import { useEffect, useRef } from "react";
import { startResilientStream, type ResilientStreamOptions } from "./resilient-stream";

export interface UseResilientStreamOptions extends Omit<
  ResilientStreamOptions,
  "fallbackAccessToken" | "resyncOnFirstOpen"
> {
  /** Reactive token; null/empty keeps the stream closed. */
  accessToken: string | null;
  streamKey?: string | null;
  enabled?: boolean;
}

export function useResilientStream(options: UseResilientStreamOptions) {
  const ref = useRef(options);
  ref.current = options;
  const { accessToken, streamKey, enabled = true } = options;
  const hasOpenedRef = useRef(false);
  const openedKeyRef = useRef(streamKey);

  useEffect(() => {
    if (!enabled || openedKeyRef.current !== streamKey) hasOpenedRef.current = false;
    openedKeyRef.current = streamKey;
    if (!enabled || !accessToken) return;
    return startResilientStream({
      open: (args) =>
        ref.current.open({
          ...args,
          onOpen: () => {
            // A stale loop's late callback must not mark the new stream as opened.
            if (!args.signal.aborted) hasOpenedRef.current = true;
            args.onOpen();
          },
        }),
      resyncOnFirstOpen: hasOpenedRef.current,
      getAccessToken: () => ref.current.getAccessToken(),
      fallbackAccessToken: accessToken,
      refreshToken: ref.current.refreshToken ? () => ref.current.refreshToken!() : undefined,
      refreshOnStatuses: ref.current.refreshOnStatuses,
      stopOnStatuses: ref.current.stopOnStatuses,
      onResync: () => ref.current.onResync?.(),
      idleTimeoutMs: ref.current.idleTimeoutMs,
      hiddenReopenAfterMs: ref.current.hiddenReopenAfterMs,
      random: ref.current.random,
    });
  }, [enabled, accessToken, streamKey]);
}
