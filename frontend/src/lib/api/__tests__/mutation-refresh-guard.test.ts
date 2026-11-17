import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Guarda: toda mutation atualiza a tela pela camada de entidade (canônico da frota, shared-widgets;
 * 2026-11-17, auditoria de CRUD depois do incidente QUB5J53). Regra de `rules/frontend.md`
 * ("Frescor e cache"): sem invalidação a tela fica velha e a pessoa precisa dar F5; chave de query
 * escolhida à mão esquece as telas que DEPENDEM do que foi gravado.
 *
 * 1. Todo `useMutation(...)` contém `invalidateEntity`/`invalidateEntityDependents`/
 *    `invalidateEndpointDependents`, cirurgia de cache (`setQueryData`/`removeQueries`) ou o
 *    comentário `refresh-ok: <motivo>` (download, sugestão de IA: nada muda no servidor), dentro
 *    da chamada ou nas linhas de comentário logo acima dela.
 * 2. `invalidateQueries(` com chave (fora da camada de invalidação) é dívida: troque por
 *    `invalidateEntity` + `entity-dependencies.ts`. `invalidateQueries()` sem argumento (recarregar
 *    tudo, pull-to-refresh) não conta.
 *
 * O que já existia está em `src/test/mutation-refresh-baseline.json`, por arquivo. A contagem só
 * cai: subiu = código novo fora do padrão; caiu = baixe a baseline
 * (`UPDATE_MUTATION_REFRESH_BASELINE=1 bunx vitest run <este arquivo>`).
 * Leitura por texto (balanceando parênteses), não por AST: o TS 7 (tsgo) não expõe a API do
 * compilador e nem todo app tem o pacote `typescript`.
 */

// `process.cwd()` e não `import.meta.url`: sob jsdom o `import.meta.url` não é `file:`.
const FRONTEND_DIR = process.cwd();
const SRC_DIR = join(FRONTEND_DIR, "src");
const BASELINE_PATH = join(SRC_DIR, "test", "mutation-refresh-baseline.json");
const UPDATE_ENV_VAR = "UPDATE_MUTATION_REFRESH_BASELINE";

const SOURCE_FILE = /\.(ts|tsx)$/;
const SKIPPED_FILE = /(\.test\.|\.spec\.|routeTree\.gen\.ts$)/;
const SKIPPED_DIRS = new Set(["__tests__", "test", "node_modules"]);
/** A camada de invalidação em si (e o realtime canônico, que invalida por entidade registrada). */
const RAW_INVALIDATE_HOME = [
  "src/lib/api/invalidation.ts",
  "src/hooks/useCrud.ts",
  "src/lib/realtime/",
];

const MUTATION_CALL = /\buseMutation\s*(<[^(]*>)?\s*\(/g;
// `<[^(]*>` = optional type argument: `setQueryData<Row[]>(` is cache surgery too.
const REFRESH_EVIDENCE =
  /\binvalidate\w*\s*(<[^(]*>)?\s*\(|\.(setQueryData|removeQueries)\s*(<[^(]*>)?\s*\(|refresh-ok:\s*\S/;
const REFRESH_OK_COMMENT = /refresh-ok:\s*\S/;
const COMMENT_LINE = /^\s*(\/\/|\/\*|\*)/;
const RAW_INVALIDATE_WITH_KEY = /\.invalidateQueries\s*\(\s*(?!\))/g;

type FileCounts = Record<string, number>;
interface RefreshBaseline {
  mutationsWithoutRefresh: FileCounts;
  rawInvalidateQueries: FileCounts;
}

function listSourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return SKIPPED_DIRS.has(entry.name) ? [] : listSourceFiles(path);
    return SOURCE_FILE.test(entry.name) && !SKIPPED_FILE.test(entry.name) ? [path] : [];
  });
}

/** Texto de `(` até o `)` que o fecha, pulando strings, template literals e comentários. */
function readCallArguments(source: string, openParen: number): string {
  const modes: string[] = [];
  const exprBraces: number[] = [];
  let depth = 0;
  for (let i = openParen; i < source.length; i++) {
    const ch = source[i];
    const next = source[i + 1];
    const mode = modes.at(-1);
    if (mode === "//") {
      if (ch === "\n") modes.pop();
    } else if (mode === "/*") {
      if (ch === "*" && next === "/") (modes.pop(), i++);
    } else if (mode === '"' || mode === "'") {
      if (ch === "\\") i++;
      else if (ch === mode) modes.pop();
    } else if (mode === "`") {
      if (ch === "\\") i++;
      else if (ch === "`") modes.pop();
      else if (ch === "$" && next === "{") (modes.push("${"), exprBraces.push(0), i++);
    } else if (ch === "/" && (next === "/" || next === "*")) {
      modes.push(`/${next}`);
      i++;
    } else if (ch === '"' || ch === "'" || ch === "`") {
      modes.push(ch);
    } else if (mode === "${" && ch === "}" && exprBraces.at(-1) === 0) {
      modes.pop();
      exprBraces.pop();
    } else {
      if (mode === "${" && (ch === "{" || ch === "}"))
        exprBraces.push(exprBraces.pop()! + (ch === "{" ? 1 : -1));
      if (ch === "(") depth++;
      if (ch === ")" && --depth === 0) return source.slice(openParen, i + 1);
    }
  }
  return source.slice(openParen);
}

/** Linhas de comentário contíguas logo acima da linha de `index` (onde se justifica a chamada). */
function leadingComment(source: string, index: number): string {
  const above = source.slice(0, source.lastIndexOf("\n", index) + 1).split("\n");
  above.pop();
  const block: string[] = [];
  for (let i = above.length - 1; i >= 0 && COMMENT_LINE.test(above[i]); i--)
    block.unshift(above[i]);
  return block.join("\n");
}

function lineOf(source: string, index: number): number {
  return source.slice(0, index).split("\n").length;
}

type RuleName = keyof RefreshBaseline;
type FileLines = Record<string, string[]>;
interface Scan {
  counts: RefreshBaseline;
  lines: Record<RuleName, FileLines>;
}

function scanSources(): Scan {
  const counts: RefreshBaseline = { mutationsWithoutRefresh: {}, rawInvalidateQueries: {} };
  const lines: Scan["lines"] = { mutationsWithoutRefresh: {}, rawInvalidateQueries: {} };
  for (const file of listSourceFiles(SRC_DIR)) {
    const rel = relative(FRONTEND_DIR, file).replaceAll("\\", "/");
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(MUTATION_CALL)) {
      const args = readCallArguments(source, match.index + match[0].length - 1);
      if (REFRESH_EVIDENCE.test(args)) continue;
      if (REFRESH_OK_COMMENT.test(leadingComment(source, match.index))) continue;
      counts.mutationsWithoutRefresh[rel] = (counts.mutationsWithoutRefresh[rel] ?? 0) + 1;
      (lines.mutationsWithoutRefresh[rel] ??= []).push(`${rel}:${lineOf(source, match.index)}`);
    }
    if (RAW_INVALIDATE_HOME.some((home) => rel.startsWith(home))) continue;
    for (const match of source.matchAll(RAW_INVALIDATE_WITH_KEY)) {
      counts.rawInvalidateQueries[rel] = (counts.rawInvalidateQueries[rel] ?? 0) + 1;
      (lines.rawInvalidateQueries[rel] ??= []).push(`${rel}:${lineOf(source, match.index)}`);
    }
  }
  return { counts, lines };
}

function readBaseline(): RefreshBaseline {
  if (!existsSync(BASELINE_PATH)) return { mutationsWithoutRefresh: {}, rawInvalidateQueries: {} };
  return JSON.parse(readFileSync(BASELINE_PATH, "utf8")) as RefreshBaseline;
}

function sortedCounts(counts: FileCounts): FileCounts {
  return Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)));
}

function ratchetProblems(scan: Scan, baseline: RefreshBaseline, rule: RuleName): string[] {
  const current = scan.counts[rule];
  const allowed = baseline[rule];
  const lines = scan.lines[rule];
  const files = new Set([...Object.keys(current), ...Object.keys(allowed)]);
  return [...files].sort().flatMap((file) => {
    const now = current[file] ?? 0;
    const was = allowed[file] ?? 0;
    if (now > was) return [`${file}: ${now} (baseline ${was})`, ...(lines[file] ?? [])];
    if (now < was) return [`${file}: caiu para ${now}, baixe a baseline (era ${was})`];
    return [];
  });
}

describe("mutation refresh guard", () => {
  const scan = scanSources();

  if (process.env[UPDATE_ENV_VAR] === "1") {
    it("reescreve a baseline", () => {
      const body = {
        mutationsWithoutRefresh: sortedCounts(scan.counts.mutationsWithoutRefresh),
        rawInvalidateQueries: sortedCounts(scan.counts.rawInvalidateQueries),
      };
      writeFileSync(BASELINE_PATH, `${JSON.stringify(body, null, 2)}\n`);
      expect(existsSync(BASELINE_PATH)).toBe(true);
    });
    return;
  }

  const baseline = readBaseline();

  it("toda useMutation atualiza a tela (invalidateEntity, cirurgia de cache ou refresh-ok)", () => {
    expect(ratchetProblems(scan, baseline, "mutationsWithoutRefresh")).toEqual([]);
  });

  it("invalidateQueries com chave à mão não cresce (use invalidateEntity)", () => {
    expect(ratchetProblems(scan, baseline, "rawInvalidateQueries")).toEqual([]);
  });

  it("o leitor entende template literal, comentário e parênteses aninhados", () => {
    const source = "useMutation({ fn: () => f(`a ${g(1)} )`), // ) refresh-ok: x\n })";
    expect(readCallArguments(source, source.indexOf("("))).toBe(source.slice(source.indexOf("(")));
    expect(REFRESH_EVIDENCE.test(source)).toBe(true);
  });

  it("cirurgia de cache com argumento de tipo também conta (setQueryData<T>)", () => {
    expect(REFRESH_EVIDENCE.test("qc.setQueryData<Row[]>(key, (rows) => rows)")).toBe(true);
    expect(REFRESH_EVIDENCE.test("qc.getQueryData<Row[]>(key)")).toBe(false);
  });

  it("refresh-ok vale também no comentário logo acima da chamada, não mais longe", () => {
    const source = "const a = 1;\n// refresh-ok: download\n  return useMutation({});\n";
    const far = "// refresh-ok: download\nconst a = 1;\nreturn useMutation({});\n";
    expect(leadingComment(source, source.indexOf("useMutation"))).toContain("refresh-ok: download");
    expect(leadingComment(far, far.indexOf("useMutation"))).toBe("");
  });
});
