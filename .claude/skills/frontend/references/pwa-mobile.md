# PWA instalado no celular — recarga, safe-area, iOS

O app adicionado à tela de início **não tem F5, não tem barra de endereço e não tem
pull-to-refresh do navegador**. Sem afordância própria, o usuário fica preso com dado velho
e a única saída é fechar e reabrir. Este arquivo é o contrato mínimo para instalar sem quebrar.

Sem `vite-plugin-pwa`, sem cache offline, sem dependência nova — tudo aqui é manifest, meta tag,
CSS, dois hooks, o item "Instalar app" (§6) e um `sw.js` push-only registrado no boot.

## 1. Manifest — `display: minimal-ui`

```json
{
  "short_name": "Projeto",
  "name": "Projeto — o que ele faz",
  "icons": [
    { "src": "logo192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "logo512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "logo512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ],
  "start_url": "/",
  "scope": "/",
  "display": "minimal-ui",
  "orientation": "portrait",
  "lang": "pt-BR",
  "theme_color": "#<cor da marca>",
  "background_color": "#ffffff"
}
```

- **`minimal-ui` > `standalone`**: no Android/Chrome o modo mínimo mantém uma barra fina **com
  botão de recarregar**. O iOS **ignora** `minimal-ui` e abre standalone mesmo assim — por isso
  a afordância in-app (§3) é obrigatória, não um extra.
- `name`/`short_name` **reais** — placeholder de scaffold (`"TanStack App"`) é o nome que o
  usuário vê no celular dele.
- `maskable` separado do `any`: sem ele o Android recorta o ícone com moldura branca.
- `scope` presente, senão navegação para fora do escopo abre no navegador e a sessão "some".

## 2. `index.html` — meta tags

```html
<meta name="viewport"
      content="width=device-width, initial-scale=1.0, viewport-fit=cover, interactive-widget=resizes-content" />
<meta name="theme-color" content="#<cor da marca>" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="Projeto" />
<link rel="apple-touch-icon" href="/logo192.png" />
<link rel="manifest" href="/manifest.json" />
```

`viewport-fit=cover` é **app-wide**: a viewport passa a incluir as faixas do notch e do home
indicator, então as compensações de safe-area (§4) entram no MESMO commit — senão conteúdo
fica embaixo do notch. `interactive-widget=resizes-content` é o par do `FormDialog`
(`mobile-keyboard.md`).

## 3. Detectar instalado + afordância de recarga

```typescript
// hooks/useIsStandalone.ts
const INSTALLED_DISPLAY_QUERY = "(display-mode: standalone), (display-mode: minimal-ui)";

function getSnapshot(): boolean {
  // `navigator.standalone` é a ÚNICA pista no iOS: o Safari nunca implementou a
  // media query `display-mode`, então o app da tela de início é indistinguível
  // de uma aba comum para o CSS.
  const iosStandalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  return iosStandalone || window.matchMedia(INSTALLED_DISPLAY_QUERY).matches;
}

export function useIsStandalone(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
```

As **duas** condições importam: `minimal-ui` no Android (senão o botão some justamente onde o
manifest pediu modo mínimo) e `navigator.standalone` no iOS.

O botão de recarregar mora no header e **só aparece instalado** (no navegador é ruído — F5 já
resolve). Ele recarrega os **dados**, não a página:

```typescript
await queryClient.invalidateQueries();   // ✅
location.reload();                       // ❌ descarta o bundle E o access em memória
```

`location.reload()` força um bootstrap inteiro (novo refresh, novo `/me`) — lento no celular e
sem ganho nenhum.

## 4. Safe-area e overscroll

```css
body {
  /* iOS faz rubber-band no documento inteiro; instalado, isso parece um
     pull-to-refresh que nunca recarrega. `contain` prende o overscroll ao
     scroller tocado — quem recarrega é o hook, não o gesto do sistema. */
  overscroll-behavior-y: contain;
}
```

Com `viewport-fit=cover`, o shell paga a conta do notch: `padding-top: env(safe-area-inset-top)`
no header fixo, `padding-bottom: max(env(safe-area-inset-bottom), .75rem)` em footer/barra de
ação, `padding-left/right` em conteúdo full-bleed (landscape com notch lateral).

## 5. Pull-to-refresh próprio

Gesto no scroller do layout (o `<main>`), não no documento. Regras que não são negociáveis:

- Engata **só** com `scrollTop <= 0` e **um** dedo (dois é pinch).
- Todos os listeners `{ passive: true }` e **nunca** `preventDefault()` — cancelar aqui trava a
  rolagem nativa no iOS. Como o gesto só engata no topo, a rolagem normal segue intocada.
- Resistência (~0.5 do deslocamento), threshold (~72px) e teto (~110px) são constantes nomeadas.
- No fim do gesto além do threshold: `invalidateQueries()` — mesma ação do botão.

## 6. Instalar app — obrigatório em todo app real (padrão da frota, 2026-10-07)

**Onde:** **SÓ** no menu do usuário, no rodapé da sidebar (canto inferior esquerdo), na área
logada — item "Instalar app" antes do "Sair". **Nunca** na tela de login, nunca na landing, nunca
no header (o slot do header é do botão de recarregar). Decisão do usuário: quem instala é quem já
usa; o app instalado abre direto no painel.

**Como (código canônico nesta pasta — copie, só troque ícones pela lib do app):**

- `install-prompt.ts` → `src/lib/pwa/install-prompt.ts`: `initInstallPrompt()` chamado no
  `main.tsx` **antes do render** (o `beforeinstallprompt` dispara uma vez, cedo, e some se ninguém
  escutar); `preventDefault()` + guarda o evento numa store vanilla lida via
  `useSyncExternalStore`; `appinstalled` limpa; `promptNativeInstall()` usa o evento uma vez.
- `pwa-platform.ts` → `src/lib/pwa/platform.ts`: `isIosDevice()` — iPadOS 13+ se diz `Macintosh`
  no UA; a pista é `Macintosh` + `navigator.maxTouchPoints > 1`. Use o MESMO helper no
  `usePushSubscription` (o `/iPad|iPhone/` cru erra o iPad).
- `install-app-button.tsx` → `src/components/pwa/InstallAppButton.tsx`: `InstallAppMenuItem`
  (Android/desktop → prompt nativo; iPhone/iPad → abre o dialog) e `InstallInstructionsDialog`
  (Compartilhar → Adicionar à Tela de Início → Adicionar; "só no Safari"). O item **some** quando
  já instalado (`useIsStandalone`) ou quando não há como instalar (sem prompt e não iOS).
- **O dialog é IRMÃO do `DropdownMenu`** (dentro do mesmo `SidebarMenuItem`, depois de
  `</DropdownMenu>`): o item do menu desmonta quando o menu fecha e levaria um dialog filho junto.
- **Service worker:** `public/sw.js` **push-only, sem `fetch` handler** (= sem cache offline) e
  `registerServiceWorkerAtBoot()` em `src/lib/push/register-sw.ts`, chamado pelo
  `initInstallPrompt()` — "fire and forget", nunca lança, não espera `ready`. App sem push usa o
  mesmo `sw.js` vazio de handlers (só existe para a instalabilidade em Chromium mais antigo).

```ts
/** Registro "fire and forget" no boot — instalabilidade do PWA. Nunca lança. */
export async function registerServiceWorkerAtBoot(): Promise<void> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  try {
    await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  } catch {
    // Sem SW o app só perde a instalabilidade; nunca pode quebrar o boot.
  }
}
```

**Armadilha (achada no optimuslar, 2026-10-07):** `overscroll-behavior-y: contain` no `body` sem o
`usePullToRefresh` ligado no `<main>` do layout = app instalado **sem gesto nenhum** de recarregar
(o `contain` mata o pull nativo). Os dois andam juntos, sempre no layout autenticado.

## 7. Testes

- **vitest**: `mockDisplayMode(installed)` do `auth-harness` → botão presente instalado,
  ausente no navegador; gesto além do threshold chama `invalidateQueries`, abaixo não chama.
  jsdom não tem `TouchEvent` nem casa `matchMedia` sozinho — os dois precisam de stub.
- **Playwright** (é onde o iOS se prova): project `iphone` (`devices["iPhone 15"]`, WebKit) —
  app carrega sem chrome de browser, botão de reload aparece, pull recarrega os dados, nada sob
  o notch nem sob o home indicator; project `android` (Pixel 7, Chromium) — `minimal-ui` expõe
  a barra com reload.

## Don'ts

- **NUNCA** `display: standalone` sem afordância de recarga in-app — é o app que "trava" no
  celular e não recarrega de jeito nenhum.
- **NUNCA** `location.reload()` como botão de atualizar (§3).
- **NUNCA** `viewport-fit=cover` sem as compensações de safe-area no mesmo commit.
- **NUNCA** `preventDefault()` no `touchmove` do pull-to-refresh (trava o scroll do iOS).
- **NUNCA** deixar `name`/`short_name`/`theme_color` de scaffold no manifest.
- **NUNCA** `fetch` handler / cache offline no `sw.js` "de brinde" — cache sem estratégia de
  invalidação serve bundle velho e vira bug de sessão fantasma. Só com pedido explícito e plano de
  versionamento. (O `sw.js` push-only registrado no boot do §6 é o padrão, não é isso.)
- **NUNCA** botão "Instalar app" no login, na landing ou no header (§6).
