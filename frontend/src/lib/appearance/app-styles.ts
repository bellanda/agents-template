/**
 * Catálogo dos estilos visuais que cada pessoa escolhe no topo do app (ref app-styles).
 *
 * O estilo já carrega o modo: não existe "App claro" + botão escuro — cada combinação que vale a
 * pena é um item. As cores vivem em `styles/themes/<id>.css` (o par `app-claro`/`app-escuro` são
 * o `:root` e o `.dark` do `styles.css`); aqui fica só o que o JS precisa: nome, modo e a cor da
 * barra do celular. Estilo novo entra também no `AppStyleId` do backend
 * (`schemas/accounts/accounts.py`) — `app-styles.test.ts` amarra os três lugares.
 *
 * O slug do TEMPLATE é `app` (ids `app-claro`/`app-escuro`). Um app novo criado a partir dele
 * renomeia `app-` para o próprio slug aqui, em `styles/themes/` e no backend.
 */
export type AppStyleMode = "light" | "dark";

export interface AppStyle {
  id: string;
  name: string;
  mode: AppStyleMode;
  /** `<meta name="theme-color">` — barra de status do celular e do app instalado. */
  themeColor: string;
}

export const APP_STYLES = [
  { id: "app-claro", name: "App claro", mode: "light", themeColor: "#ffffff" },
  { id: "nitido", name: "Nítido", mode: "light", themeColor: "#f6f8fa" },
  { id: "grafite", name: "Grafite", mode: "light", themeColor: "#1e2220" },
  { id: "areia", name: "Areia", mode: "light", themeColor: "#fcfaf7" },
  { id: "app-escuro", name: "App escuro", mode: "dark", themeColor: "#010409" },
  { id: "escuro-suave", name: "Escuro suave", mode: "dark", themeColor: "#151b23" },
  { id: "carbono", name: "Carbono", mode: "dark", themeColor: "#0b0a09" },
  { id: "alto-contraste", name: "Alto contraste", mode: "dark", themeColor: "#010409" },
] as const satisfies readonly AppStyle[];

export type AppStyleId = (typeof APP_STYLES)[number]["id"];

export const DEFAULT_APP_STYLE: AppStyleId = "app-claro";

/** Estilo escuro de identidade: destino de quem já usava o escuro do `ThemeProvider` antigo. */
export const LEGACY_DARK_APP_STYLE: AppStyleId = "app-escuro";

export function isAppStyleId(value: unknown): value is AppStyleId {
  return APP_STYLES.some((style) => style.id === value);
}

export function findAppStyle(id: AppStyleId): (typeof APP_STYLES)[number] {
  return APP_STYLES.find((style) => style.id === id) ?? APP_STYLES[0];
}
