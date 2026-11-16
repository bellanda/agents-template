import { useCallback, useEffect, useRef, useState } from "react";

// Deslocamento (px, já com resistência) que dispara a recarga.
const PULL_THRESHOLD_PX = 72;
// Teto do indicador — puxar além disso não estica mais nada.
const PULL_MAX_PX = 110;
// Fração do movimento do dedo que vira deslocamento visível.
const PULL_RESISTANCE = 0.5;

interface PullToRefreshResult {
  /** Ref de callback para o elemento que rola (o `<main>` do layout). */
  scrollRef: (node: HTMLElement | null) => void;
  pullDistance: number;
  isRefreshing: boolean;
}

/**
 * Pull-to-refresh próprio, para o app instalado — onde não existe F5 e o gesto
 * do navegador não chega (o documento não rola; quem rola é o `<main>`).
 *
 * Todos os listeners são `{ passive: true }` e NUNCA chamam `preventDefault()`:
 * o gesto só engata com o scroller já no topo, então a rolagem nativa segue
 * intocada. Cancelar o evento aqui travaria o scroll no iOS.
 */
export function usePullToRefresh(onRefresh: () => Promise<unknown> | void): PullToRefreshResult {
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const onRefreshRef = useRef(onRefresh);
  const distanceRef = useRef(0);

  useEffect(() => {
    onRefreshRef.current = onRefresh;
  }, [onRefresh]);

  const scrollRef = useCallback((node: HTMLElement | null) => {
    if (!node) return;

    let startY = 0;
    let pulling = false;

    const setDistance = (value: number) => {
      distanceRef.current = value;
      setPullDistance(value);
    };

    const handleTouchStart = (event: TouchEvent) => {
      // Um dedo só (dois é pinch/zoom) e com o scroller no topo — senão o gesto
      // é rolagem normal e não pode ser sequestrado.
      pulling = node.scrollTop <= 0 && event.touches.length === 1;
      startY = event.touches[0].clientY;
      setDistance(0);
    };

    const handleTouchMove = (event: TouchEvent) => {
      if (!pulling) return;
      const delta = event.touches[0].clientY - startY;
      if (delta <= 0 || node.scrollTop > 0) {
        pulling = false;
        setDistance(0);
        return;
      }
      setDistance(Math.min(delta * PULL_RESISTANCE, PULL_MAX_PX));
    };

    const handleTouchEnd = async () => {
      if (!pulling) return;
      pulling = false;
      const reachedThreshold = distanceRef.current >= PULL_THRESHOLD_PX;
      setDistance(0);
      if (!reachedThreshold) return;

      setIsRefreshing(true);
      try {
        await onRefreshRef.current();
      } finally {
        setIsRefreshing(false);
      }
    };

    node.addEventListener("touchstart", handleTouchStart, { passive: true });
    node.addEventListener("touchmove", handleTouchMove, { passive: true });
    node.addEventListener("touchend", handleTouchEnd, { passive: true });
    node.addEventListener("touchcancel", handleTouchEnd, { passive: true });

    return () => {
      node.removeEventListener("touchstart", handleTouchStart);
      node.removeEventListener("touchmove", handleTouchMove);
      node.removeEventListener("touchend", handleTouchEnd);
      node.removeEventListener("touchcancel", handleTouchEnd);
    };
  }, []);

  return { scrollRef, pullDistance, isRefreshing };
}
