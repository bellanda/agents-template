/**
 * Catálogo dos estilos visuais que cada pessoa escolhe no topo do app (ref app-styles).
 *
 * O estilo já carrega o modo: não existe "Nítido" + botão escuro — cada combinação que vale a
 * pena é um item. Nítido e Escuro suave substituíram o par de identidade App claro/escuro
 * (branco e preto puros, decisão do usuário 2026-11-10); os demais ficam, todos suavizados na
 * mesma régua (exceção de propósito: Alto contraste). As cores vivem em `styles/themes/<id>.css`;
 * aqui fica só o que o JS precisa: nome, modo e a cor da barra do celular. Estilo novo entra
 * também no `AppStyleId` do backend (`schemas/accounts/accounts.py`) — `app-styles.test.ts`
 * amarra os três lugares.
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
  { id: "nitido", name: "Nítido", mode: "light", themeColor: "#f6f8fa" },
  { id: "grafite", name: "Grafite", mode: "light", themeColor: "#1e2220" },
  { id: "areia", name: "Areia", mode: "light", themeColor: "#fcfaf7" },
  { id: "escuro-suave", name: "Escuro suave", mode: "dark", themeColor: "#151b23" },
  { id: "carbono", name: "Carbono", mode: "dark", themeColor: "#1c1a19" },
  { id: "alto-contraste", name: "Alto contraste", mode: "dark", themeColor: "#010409" },
] as const satisfies readonly AppStyle[];

export type AppStyleId = (typeof APP_STYLES)[number]["id"];

export const DEFAULT_APP_STYLE: AppStyleId = "nitido";

/** Destino de quem já usava o escuro do `ThemeProvider` antigo (o par de identidade saiu em 2026-11-10). */
export const LEGACY_DARK_APP_STYLE: AppStyleId = "escuro-suave";

export function isAppStyleId(value: unknown): value is AppStyleId {
  return APP_STYLES.some((style) => style.id === value);
}

export function findAppStyle(id: AppStyleId): (typeof APP_STYLES)[number] {
  return APP_STYLES.find((style) => style.id === id) ?? APP_STYLES[0];
}
