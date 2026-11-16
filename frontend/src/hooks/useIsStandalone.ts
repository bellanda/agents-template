import { useSyncExternalStore } from "react";

// `minimal-ui` entra junto: o manifest pede esse modo, e o Chrome do Android
// reporta `display-mode: minimal-ui` (não `standalone`) quando o app foi
// instalado. Ficar só em `standalone` esconderia a afordância no Android.
const INSTALLED_DISPLAY_QUERY = "(display-mode: standalone), (display-mode: minimal-ui)";

function subscribe(onChange: () => void) {
  const media = window.matchMedia(INSTALLED_DISPLAY_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  // `navigator.standalone` é a ÚNICA pista no iOS: o Safari nunca implementou a
  // media query `display-mode`, então o app aberto pela tela de início é
  // indistinguível de uma aba comum para o CSS.
  const iosStandalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return iosStandalone || window.matchMedia(INSTALLED_DISPLAY_QUERY).matches;
}

/** `true` quando o app roda instalado (tela de início), não dentro do navegador. */
export function useIsStandalone(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
