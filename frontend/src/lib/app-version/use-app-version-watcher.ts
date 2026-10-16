import {
  CHECK_INTERVAL_MS,
  COUNTDOWN_SECONDS,
  createPreloadErrorHandler,
  decideUpdateAction,
  fetchDeployedBuildId,
  hasReloadedFor,
  isCountdownPaused,
  markReloadedFor,
} from "@/lib/app-version/app-version";
import { useRouter } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Monta UMA vez no root. Detecta deploy novo e troca o bundle (contrato em `app-version.ts`).
 * Em dev (`bun dev`) não há version.json nem chunks com hash: vira no-op.
 */
export function useAppVersionWatcher() {
  const router = useRouter();
  const [deployedBuildId, setDeployedBuildId] = useState<string | null>(null);
  const [isHidden, setIsHidden] = useState(() => document.visibilityState === "hidden");
  const [secondsLeft, setSecondsLeft] = useState(COUNTDOWN_SECONDS);
  const updatePending = deployedBuildId !== null;
  const reloadBlocked = updatePending && hasReloadedFor(deployedBuildId);
  const action = decideUpdateAction({
    updatePending,
    isHidden,
    isNavigating: false,
    reloadBlocked,
  });
  const deployedRef = useRef<string | null>(null);
  deployedRef.current = deployedBuildId;

  const reloadNow = useCallback(() => {
    if (deployedRef.current) markReloadedFor(deployedRef.current);
    window.location.reload();
  }, []);

  useEffect(() => {
    if (!import.meta.env.PROD) return;
    const check = async () => {
      const buildId = await fetchDeployedBuildId();
      if (buildId && buildId !== __APP_BUILD_ID__) setDeployedBuildId(buildId);
    };
    const onVisibility = () => {
      setIsHidden(document.visibilityState === "hidden");
      if (document.visibilityState === "visible") void check();
    };
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") void check();
    }, CHECK_INTERVAL_MS);
    const onPreloadError = createPreloadErrorHandler(() => window.location.reload());
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("focus", check);
    window.addEventListener("vite:preloadError", onPreloadError);
    void check();
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("focus", check);
      window.removeEventListener("vite:preloadError", onPreloadError);
    };
  }, []);

  // Aba oculta com update pendente: recarrega sem o usuário ver.
  useEffect(() => {
    if (action === "reload-now") reloadNow();
  }, [action, reloadNow]);

  // Próxima navegação vira carga completa no destino (já cai no bundle novo).
  useEffect(() => {
    if (!updatePending || reloadBlocked) return;
    return router.subscribe("onBeforeNavigate", ({ toLocation }) => {
      if (deployedRef.current) markReloadedFor(deployedRef.current);
      window.location.assign(toLocation.href);
    });
  }, [router, updatePending, reloadBlocked]);

  // Contagem regressiva; pausa (sem zerar) enquanto há campo em foco ou dialog aberto.
  useEffect(() => {
    if (action !== "countdown") return;
    setSecondsLeft(COUNTDOWN_SECONDS);
    const tick = window.setInterval(() => {
      if (isCountdownPaused(document)) return;
      setSecondsLeft((current) => current - 1);
    }, 1000);
    return () => window.clearInterval(tick);
  }, [action]);

  useEffect(() => {
    if (action === "countdown" && secondsLeft <= 0) reloadNow();
  }, [action, secondsLeft, reloadNow]);

  return { updatePending, secondsLeft: action === "countdown" ? secondsLeft : null, reloadNow };
}
