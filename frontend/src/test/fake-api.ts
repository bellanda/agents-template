/**
 * Fake da API COM MEMÓRIA para teste de tela de CRUD (canônico da frota, shared-widgets;
 * 2026-11-17, incidente QUB5J53). Substitui o `client` do `useDataProvider()`: o que a tela grava
 * fica guardado, e o próximo `GET` devolve o valor novo. Assim o teste prova as duas metades que o
 * mock de hook esconde:
 * - a tela ATUALIZA depois de salvar (a mutation invalidou ou trocou o cache certo);
 * - o formulário abre preenchido pela fonte certa (o valor que a tela mostra, não uma cópia).
 *
 * ```ts
 * const api = createFakeApi({
 *   collections: { "/organizations/:orgId/contacts": [{ id: 1, name: "Ana" }] },
 *   routes: { "POST /organizations/:orgId/contacts/:id/merge": ({ params }) => ({ ok: params.id }) },
 * });
 * api.fail("PATCH /organizations/:orgId/contacts/:id", fakeApiError(409, "Conflito"));
 * ```
 *
 * Coleção = REST padrão: `GET` lista (formato `PagedResponse`, `skip`/`limit` da query), `POST`
 * cria (id novo), `GET/PATCH/PUT/DELETE /:id`. Rota própria vence a coleção. Rota sem dono lança
 * erro (o teste falha alto em vez de a tela ficar carregando). O corpo chega em camelCase, como
 * o `ApiClient` recebe da tela; a conversão snake_case é do próprio `ApiClient` e tem teste lá.
 * A resposta do PATCH é a linha mesclada, igual ao `GET`: o backend tem teste próprio de que
 * os dois batem.
 */

export type FakeMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type FakeRow = Record<string, unknown>;

export interface FakeCall {
  method: FakeMethod;
  path: string;
  body: unknown;
}

export interface FakeRouteRequest {
  params: Record<string, string>;
  query: URLSearchParams;
  body: unknown;
}

export type FakeRouteHandler = (request: FakeRouteRequest) => unknown;
export type FakeRouteData = FakeRow | FakeRow[] | string | number | boolean | null;

export interface FakeCollectionOptions {
  rows: FakeRow[];
  /** Campo de id da linha (padrão `id`). */
  idKey?: string;
  /** Monta a linha criada (defaults e campos que o servidor calcula). Padrão: body + id. */
  onCreate?: (body: FakeRow, id: string | number) => FakeRow;
}

export interface FakeApiOptions {
  collections?: Record<string, FakeRow[] | FakeCollectionOptions>;
  /** Chave "MÉTODO /caminho/:param" → resposta fixa ou função do request. */
  routes?: Record<string, FakeRouteHandler | FakeRouteData>;
}

/** Erro no formato `ApiError` da frota (`{message, status, code?, details?}`). */
export interface FakeApiError {
  message: string;
  status: number;
  code?: string;
  details?: Record<string, unknown>;
}

interface CompiledPattern {
  pattern: string;
  regex: RegExp;
}

interface Collection {
  list: CompiledPattern;
  item: CompiledPattern;
  rows: FakeRow[];
  idKey: string;
  onCreate: (body: FakeRow, id: string | number) => FakeRow;
}

interface Route {
  method: FakeMethod;
  path: CompiledPattern;
  value: unknown;
}

interface Failure {
  method: FakeMethod;
  path: CompiledPattern;
  error: unknown;
  remaining: number;
}

const HTTP_OK = 200;
const HTTP_CREATED = 201;
const HTTP_NOT_FOUND = 404;
const DEFAULT_PAGE_LIMIT = 50;

export function fakeApiError(
  status: number,
  message: string,
  details?: Record<string, unknown>
): FakeApiError {
  const code = typeof details?.code === "string" ? details.code : undefined;
  return { message, status, code, details };
}

/**
 * Cópia que "atravessa a rede": a tela nunca segura o objeto guardado no fake, e o fake nunca guarda
 * o objeto da tela. Sem isso, um handler que muta a linha no lugar (ou a tela que muta o dado da
 * query) faz a tela velha parecer atualizada e o teste passa sem invalidação (achado na auditoria
 * de 2026-11-17, emporion e kailos).
 */
function copyAcrossNetwork<T>(value: T): T {
  if (value instanceof FormData || value instanceof Blob) return value;
  return structuredClone(value);
}

function compilePattern(pattern: string): CompiledPattern {
  const source = normalizePath(pattern)
    .split("/")
    .map((segment) =>
      segment.startsWith(":")
        ? `(?<${segment.slice(1)}>[^/]+)`
        : segment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    )
    .join("/");
  return { pattern, regex: new RegExp(`^${source}$`) };
}

function normalizePath(path: string): string {
  const withSlash = path.startsWith("/") ? path : `/${path}`;
  return withSlash.length > 1 && withSlash.endsWith("/") ? withSlash.slice(0, -1) : withSlash;
}

function splitMethodPath(key: string): [FakeMethod, string] {
  const [method, ...rest] = key.trim().split(/\s+/);
  return [method.toUpperCase() as FakeMethod, rest.join(" ")];
}

function splitUrl(rawPath: string, params?: Record<string, unknown>) {
  const [path, search = ""] = rawPath.split("?");
  const query = new URLSearchParams(search);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null) query.set(key, String(value));
  }
  return { path: normalizePath(path), query };
}

function makeCollection(pattern: string, spec: FakeRow[] | FakeCollectionOptions): Collection {
  const options = Array.isArray(spec) ? { rows: spec } : spec;
  const idKey = options.idKey ?? "id";
  return {
    list: compilePattern(pattern),
    item: compilePattern(`${normalizePath(pattern)}/:fakeItemId`),
    rows: options.rows.map((row) => ({ ...row })),
    idKey,
    onCreate: options.onCreate ?? ((body, id) => ({ ...body, [idKey]: id })),
  };
}

function nextId(collection: Collection): string | number {
  const ids = collection.rows.map((row) => row[collection.idKey]);
  if (ids.some((id) => typeof id === "string")) return `fake-${ids.length + 1}`;
  return Math.max(0, ...ids.map((id) => Number(id) || 0)) + 1;
}

function pagedList(rows: FakeRow[], query: URLSearchParams) {
  const skip = Number(query.get("skip") ?? 0);
  const limit = Number(query.get("limit") ?? DEFAULT_PAGE_LIMIT);
  const items = rows.slice(skip, skip + limit);
  return { items, total: rows.length, skip, limit, hasMore: skip + items.length < rows.length };
}

export function createFakeApi(options: FakeApiOptions = {}) {
  const calls: FakeCall[] = [];
  const failures: Failure[] = [];
  const collections = Object.entries(options.collections ?? {}).map(([pattern, spec]) =>
    makeCollection(pattern, spec)
  );
  const routes: Route[] = Object.entries(options.routes ?? {}).map(([key, value]) => {
    const [method, path] = splitMethodPath(key);
    return { method, path: compilePattern(path), value };
  });

  function findRow(collection: Collection, id: string) {
    const index = collection.rows.findIndex((row) => String(row[collection.idKey]) === id);
    if (index < 0) throw fakeApiError(HTTP_NOT_FOUND, `fake-api: ${id} não existe`);
    return index;
  }

  function serveCollection(
    method: FakeMethod,
    path: string,
    query: URLSearchParams,
    body: unknown
  ) {
    for (const collection of collections) {
      if (collection.list.regex.test(path)) {
        if (method === "GET") return { data: pagedList(collection.rows, query), status: HTTP_OK };
        if (method !== "POST") continue;
        const created = collection.onCreate(body as FakeRow, nextId(collection));
        collection.rows.push(created);
        return { data: created, status: HTTP_CREATED };
      }
      const id = collection.item.regex.exec(path)?.groups?.fakeItemId;
      if (id === undefined || method === "POST") continue;
      const index = findRow(collection, id);
      if (method === "DELETE") {
        collection.rows.splice(index, 1);
        return { data: null, status: HTTP_OK };
      }
      const current = collection.rows[index];
      if (method === "PATCH") collection.rows[index] = { ...current, ...(body as FakeRow) };
      if (method === "PUT")
        collection.rows[index] = {
          ...(body as FakeRow),
          [collection.idKey]: current[collection.idKey],
        };
      return { data: collection.rows[index], status: HTTP_OK };
    }
    return null;
  }

  function throwPlannedFailure(method: FakeMethod, path: string) {
    const failure = failures.find(
      (candidate) => candidate.method === method && candidate.path.regex.test(path)
    );
    if (!failure) return;
    failure.remaining -= 1;
    if (failure.remaining <= 0) failures.splice(failures.indexOf(failure), 1);
    throw failure.error;
  }

  function dispatch(
    method: FakeMethod,
    rawPath: string,
    body?: unknown,
    params?: Record<string, unknown>
  ) {
    const { path, query } = splitUrl(rawPath, params);
    const sent = copyAcrossNetwork(body);
    calls.push({ method, path: rawPath, body: sent });
    throwPlannedFailure(method, path);
    for (const route of routes) {
      const match = route.method === method ? route.path.regex.exec(path) : null;
      if (!match) continue;
      const data =
        typeof route.value === "function"
          ? (route.value as FakeRouteHandler)({ params: { ...match.groups }, query, body: sent })
          : route.value;
      return { data: copyAcrossNetwork(data), status: HTTP_OK, success: true };
    }
    const served = serveCollection(method, path, query, copyAcrossNetwork(sent));
    if (served) return { ...served, data: copyAcrossNetwork(served.data), success: true };
    throw new Error(`fake-api: ${method} ${rawPath} não mapeado`);
  }

  type Config = { params?: Record<string, unknown>; data?: unknown };
  const client = {
    get: async (path: string, config?: Config) => dispatch("GET", path, undefined, config?.params),
    post: async (path: string, body?: unknown, config?: Config) =>
      dispatch("POST", path, body, config?.params),
    put: async (path: string, body?: unknown, config?: Config) =>
      dispatch("PUT", path, body, config?.params),
    patch: async (path: string, body?: unknown, config?: Config) =>
      dispatch("PATCH", path, body, config?.params),
    // Like axios: a DELETE body travels in `config.data`, the query in `config.params`.
    delete: async (path: string, config?: Config) =>
      dispatch("DELETE", path, config?.data, config?.params),
    upload: async (path: string, body: FormData) => dispatch("POST", path, body),
    getBlob: async (path: string) => {
      dispatch("GET", path);
      return new Blob(["arquivo"], { type: "application/octet-stream" });
    },
  };

  function collectionRows(pattern: string): FakeRow[] {
    const collection = collections.find((candidate) => candidate.list.pattern === pattern);
    if (!collection) throw new Error(`fake-api: coleção ${pattern} não declarada`);
    return collection.rows;
  }

  return {
    client,
    calls,
    /** Linhas atuais da coleção (o "banco" do fake), para conferir o que a tela gravou. */
    rows: collectionRows,
    /** Próximas `times` chamadas que casam `"MÉTODO /caminho/:param"` lançam `error`. */
    fail(key: string, error: unknown, times = 1) {
      const [method, path] = splitMethodPath(key);
      failures.push({ method, path: compilePattern(path), error, remaining: times });
    },
    bodyOf: (method: FakeMethod, pathPart: string) =>
      calls.filter((call) => call.method === method && call.path.includes(pathPart)).at(-1)?.body,
    countOf: (method: FakeMethod, pathPart: string) =>
      calls.filter((call) => call.method === method && call.path.includes(pathPart)).length,
  };
}

export type FakeApi = ReturnType<typeof createFakeApi>;
