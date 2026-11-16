/**
 * Service worker mínimo da frota: existe só para o app ser INSTALÁVEL (Chromium mais antigo
 * exige SW ativo) e como ponto de partida do push.
 *
 * NÃO existe handler de `fetch`, precache nem Cache API aqui, e isso é deliberado: cachear o
 * bundle reintroduziria o bug que o `AppReloadButton` e o `usePullToRefresh` combatem (app
 * instalado no iOS, sem F5, servindo JavaScript velho para sempre). `skipWaiting()` +
 * `clients.claim()` só são seguros PORQUE não há precache.
 *
 * App com push: o handler `push`/`notificationclick` vem do `sw.js` do kailos (referência
 * da frota); este arquivo fica em `public/` para não ganhar hash no nome e deve ser servido com
 * `Cache-Control: no-store`.
 */
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
