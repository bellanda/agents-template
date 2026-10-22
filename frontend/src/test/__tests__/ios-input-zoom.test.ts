import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Regressão 2026-10-22 (Promocar, iPhone): o campo do chat tinha `text-[15px]`. O Safari do iOS
 * dá zoom na página ao focar campo com fonte < 16px e não desfaz ao fechar o teclado: a conversa
 * ficava "fora de padrão" e o X do visualizador de foto saía da tela (só com pinça). Regra:
 * campo nativo é `text-base` no celular; tamanho menor só com prefixo `md:`/`lg:`/`xl:`. `(?:=>|[^>])` atravessa arrow functions (`onChange={(e) => …}`) antes do `className` — com `[^>]` puro elas escondiam o campo (emporion, 2026-10-22).
 */
const SRC = join(__dirname, "..", "..");
const FIELD_TAG =
  /<(Input|Textarea|input|textarea)\b(?:=>|[^>])*?className=(["'`{])([\s\S]*?)(?:\2|\})/g;
const SMALL_TEXT = /(?:^|\s)(text-xs|text-sm|text-\[(?:[0-9]|1[0-5])px\])(?=\s|$|["'`])/g;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "__tests__" ? [] : sourceFiles(path);
    return path.endsWith(".tsx") && !path.endsWith(".test.tsx") ? [path] : [];
  });
}

describe("campo de digitação no celular", () => {
  it("nenhum Input/Textarea usa fonte < 16px sem prefixo de breakpoint", () => {
    const offenders = sourceFiles(SRC).flatMap((file) =>
      [...readFileSync(file, "utf8").matchAll(FIELD_TAG)].flatMap((tag) =>
        [...tag[3]!.matchAll(SMALL_TEXT)].map((m) => `${relative(SRC, file)}: ${m[1]}`)
      )
    );
    expect(offenders).toEqual([]);
  });
});
