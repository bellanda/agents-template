import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Guard: nenhum endpoint da nossa própria API pode ser chamado com `fetch` cru.
 *
 * Chamada fora do `apiFetch` não anexa o Bearer (o access token vive em memória)
 * e não passa pelo retry-on-401 — é exatamente o que fazia o CRUD dar erro quando
 * o access expirava no meio da sessão e só voltar com F5. `fetch` direto só para
 * API externa (BrasilAPI, ViaCEP, IBGE) e para os casos da allowlist abaixo.
 */

// `process.cwd()` e não `import.meta.url`: sob jsdom o `import.meta.url` não é
// uma URL `file:`, e o vitest sempre roda a partir da raiz do frontend.
const SRC_DIR = join(process.cwd(), "src");

/** Se um destes aparece no argumento do `fetch`, a URL é da nossa API. */
const OWN_API_MARKERS = [/API_BASE/, /ACCOUNTS_BASE/, /UPLOADS_BASE_URL/, /["'`]\/api\//];

/** Quanto do código depois de `fetch(` entra na análise do argumento. */
const ARGUMENT_SCAN_CHARS = 200;

const ALLOWLIST: ReadonlyArray<{ file: string; reason: string }> = [
  {
    file: "src/lib/api/client.ts",
    reason: "É o próprio apiFetch — o único lugar onde o fetch cru mora.",
  },
  {
    file: "src/lib/observability/client-logger.ts",
    reason:
      "Log de erro do front: não pode anexar Bearer nem disparar refresh-em-401 (um 401 no log " +
      "reentraria no próprio logger).",
  },
];

function collectSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__tests__" || entry.name === "test") continue;
      out.push(...collectSourceFiles(full));
      continue;
    }
    if (/\.(ts|tsx)$/.test(entry.name) && !/\.(test|spec)\.tsx?$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function findOwnApiFetches(source: string): string[] {
  const hits: string[] = [];
  const pattern = /\bfetch\s*\(/g;
  let match = pattern.exec(source);
  while (match !== null) {
    const argument = source.slice(match.index, match.index + ARGUMENT_SCAN_CHARS);
    if (OWN_API_MARKERS.some((marker) => marker.test(argument))) {
      const line = source.slice(0, match.index).split("\n").length;
      hits.push(`linha ${line}: ${argument.split("\n")[0]?.trim()}`);
    }
    match = pattern.exec(source);
  }
  return hits;
}

describe("nenhum fetch cru em endpoint da própria API", () => {
  const allowed = new Set(ALLOWLIST.map((entry) => entry.file));

  it("todo endpoint próprio passa pelo apiFetch", () => {
    const offenders: string[] = [];

    for (const file of collectSourceFiles(SRC_DIR)) {
      const relativePath = relative(SRC_DIR, file).split("\\").join("/");
      const projectPath = `src/${relativePath}`;
      if (allowed.has(projectPath)) continue;

      const hits = findOwnApiFetches(readFileSync(file, "utf8"));
      for (const hit of hits) {
        offenders.push(`${projectPath} — ${hit}`);
      }
    }

    expect(offenders).toEqual([]);
  });

  it("a allowlist não acumula entrada morta", () => {
    const existing = new Set(
      collectSourceFiles(SRC_DIR).map(
        (file) => `src/${relative(SRC_DIR, file).split("\\").join("/")}`
      )
    );
    const stale = ALLOWLIST.filter((entry) => !existing.has(entry.file)).map((e) => e.file);

    expect(stale).toEqual([]);
  });
});
