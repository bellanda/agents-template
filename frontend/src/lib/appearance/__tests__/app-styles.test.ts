// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { APP_STYLES, DEFAULT_APP_STYLE } from "@/lib/appearance/app-styles";
import {
  bootAppStyle,
  getActiveAppStyle,
  isAppStyleChoicePending,
  markAppStyleChosen,
  resetAppStyleStoreForTests,
  setAccount,
} from "@/lib/appearance/app-style-store";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";

const SRC = resolve(__dirname, "../../..");
const BACKEND_SCHEMA = resolve(SRC, "../../backend/src/api/schemas/accounts/accounts.py");

describe("catálogo de estilos × CSS × backend", () => {
  it("nitido é o padrão e o primeiro; o par de identidade saiu e os 6 estilos existem", () => {
    const ids: string[] = APP_STYLES.map((style) => style.id);
    expect(DEFAULT_APP_STYLE).toBe("nitido");
    expect(ids).toEqual([
      "nitido",
      "grafite",
      "areia",
      "escuro-suave",
      "carbono",
      "alto-contraste",
    ]);
    expect(ids).not.toContain("app-claro");
    expect(ids).not.toContain("app-escuro");
  });

  it("todo estilo tem o CSS importado no styles.css", () => {
    const indexCss = readFileSync(resolve(SRC, "styles.css"), "utf8");
    for (const { id } of APP_STYLES) {
      readFileSync(resolve(SRC, `styles/themes/${id}.css`), "utf8"); // existe
      expect(indexCss, id).toContain(`./styles/themes/${id}.css`);
    }
  });

  it("os ids são exatamente os do AppStyleId do backend", () => {
    const source = readFileSync(BACKEND_SCHEMA, "utf8");
    const literal = source.match(/AppStyleId = Literal\[([^\]]*)\]/)?.[1] ?? "";
    const backendIds = [...literal.matchAll(/"([^"]+)"/g)].map((match) => match[1]);
    expect(backendIds).toEqual(APP_STYLES.map((style) => style.id));
  });

  it("estilo escuro e claro carregam o modo certo", () => {
    expect(APP_STYLES.filter((s) => s.mode === "dark").map((s) => s.id)).toEqual([
      "escuro-suave",
      "carbono",
      "alto-contraste",
    ]);
  });
});

describe("store do estilo", () => {
  beforeEach(() => {
    resetAppStyleStoreForTests();
    localStorage.clear();
    document.documentElement.className = "";
    document.documentElement.removeAttribute("data-style");
  });

  it("o boot pinta o estilo do cache no <html>", () => {
    localStorage.setItem("app:app-style:v1", "escuro-suave");
    bootAppStyle();
    const root = document.documentElement;
    expect(root.getAttribute("data-style")).toBe("escuro-suave");
    expect(root.classList.contains("dark")).toBe(true);
  });

  it("sem cache usa o padrão; chave antiga 'dark' migra para escuro-suave e some", () => {
    bootAppStyle();
    expect(getActiveAppStyle()).toBe(DEFAULT_APP_STYLE);

    localStorage.clear();
    localStorage.setItem("vite-ui-theme", "dark");
    bootAppStyle();
    expect(getActiveAppStyle()).toBe("escuro-suave");
    expect(localStorage.getItem("vite-ui-theme")).toBeNull();
    expect(localStorage.getItem("app:app-style:v1")).toBe("escuro-suave");
  });

  it("conta que muda reaplica, mas o mesmo valor velho não desfaz a escolha local", () => {
    bootAppStyle();
    setAccount({ userId: "u1", appStyle: "nitido" });
    expect(getActiveAppStyle()).toBe("nitido");

    setAccount({ userId: "u1", appStyle: "nitido" });
    expect(getActiveAppStyle()).toBe("nitido");
    setAccount({ userId: "u1", appStyle: "escuro-suave" });
    expect(getActiveAppStyle()).toBe("escuro-suave");
  });

  it("boas-vindas só para conta sem estilo que ainda não escolheu", () => {
    bootAppStyle();
    expect(isAppStyleChoicePending()).toBe(false); // conta ainda não carregou
    setAccount({ userId: "u1", appStyle: undefined });
    expect(isAppStyleChoicePending()).toBe(true);
    markAppStyleChosen("u1");
    expect(isAppStyleChoicePending()).toBe(false);
  });
});
