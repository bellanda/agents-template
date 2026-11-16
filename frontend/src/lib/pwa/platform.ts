/**
 * Detecção de plataforma compartilhada por push e instalação do PWA.
 *
 * iPadOS 13+ se identifica como `Macintosh` no user agent (modo "site desktop") e
 * não contém "iPad" — `/iPad/.test(userAgent)` falha nele. A pista confiável é um
 * Mac com tela multitouch (Mac de verdade reporta `maxTouchPoints === 0`).
 */
export function isIosDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  if (/iPad|iPhone|iPod/.test(navigator.userAgent)) return true;
  return /Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1;
}
