import type { QueryKey } from "@tanstack/react-query";

/**
 * Motor genérico do mapa de dependência entre entidades (auditoria 2026-11-13, core-spa-02).
 * Idêntico em toda a frota; a TABELA de cada app mora em `entity-dependencies.ts` e a API que
 * as telas usam está em `invalidation.ts`. Nada aqui conhece um app.
 *
 * Modelo: uma "entidade" é um conjunto de queries do cache (identificadas pela chave) mais a
 * lista de OUTRAS entidades cujos dados derivam dela (`dependents`). Gravar a entidade X
 * invalida X e, transitivamente, todos os dependentes (painel, relatório, contador, outro
 * módulo). Quem escreve a query nova só precisa declarar a chave aqui, uma vez.
 */
export interface EntityDefinition<N extends string = string> {
  /**
   * Recursos sob `/organizations/:orgId/<segmento>` (convenção das rotas dos apps multi-org):
   * casa a query cuja 1ª posição da chave é esse caminho ou um sub-caminho dele.
   */
  orgPaths?: readonly string[];
  /**
   * Chaves "soltas" (`["whatsapp", ...]`, `["/evaluations", ...]`): casa a 1ª posição da chave
   * igual ao valor (com ou sem `/` na frente) ou como prefixo de caminho. Vale para qualquer
   * org e para os apps single-tenant.
   */
  keys?: readonly string[];
  /** Entidades que derivam desta e precisam renovar quando ela muda. */
  dependents?: readonly N[];
}

export type EntityMap<N extends string = string> = Record<N, EntityDefinition<N>>;

/**
 * Declara a tabela com nomes de entidade tipados: `dependents` só aceita chaves da própria
 * tabela (erro de digitação vira erro de compilação, não invalidação silenciosamente perdida).
 */
export function defineEntityMap<
  const T extends Record<string, EntityDefinition<Extract<keyof T, string>>>,
>(map: T): T {
  return map;
}

/** Entidade + dependentes transitivos (tolera ciclo: A -> B -> A). */
export function entityClosure<N extends string>(map: EntityMap<N>, entity: N): Set<N> {
  const seen = new Set<N>();
  const stack: N[] = [entity];
  while (stack.length > 0) {
    const current = stack.pop() as N;
    if (seen.has(current)) continue;
    seen.add(current);
    for (const dependent of map[current]?.dependents ?? []) stack.push(dependent);
  }
  return seen;
}

function headOf(queryKey: QueryKey): string | null {
  const head = queryKey[0];
  return typeof head === "string" ? head : null;
}

function isPathOrSubpath(head: string, prefix: string): boolean {
  return head === prefix || head.startsWith(`${prefix}/`);
}

/**
 * A chave pertence a esta entidade? `orgId` nulo = org desconhecida (ex.: CRUD global como
 * `/assessments`): casa o recurso em QUALQUER org. Over-invalidar outra org é inofensivo (só a
 * org aberta tem query ativa), perder a dependência não é.
 */
export function queryBelongsTo(
  definition: EntityDefinition,
  orgId: string | null | undefined,
  queryKey: QueryKey
): boolean {
  const head = headOf(queryKey);
  if (head === null) return false;
  const orgPrefix = /^\/organizations\/([^/]+)\/(.+)$/.exec(head);
  if (orgPrefix && (!orgId || orgPrefix[1] === orgId)) {
    const rest = orgPrefix[2];
    if ((definition.orgPaths ?? []).some((segment) => isPathOrSubpath(rest, segment))) return true;
  }
  const bare = head.startsWith("/") ? head.slice(1) : head;
  return (definition.keys ?? []).some((key) => isPathOrSubpath(bare, key.replace(/^\//, "")));
}

/** Predicado de `invalidateQueries` para um conjunto de entidades. */
export function entitiesPredicate<N extends string>(
  map: EntityMap<N>,
  orgId: string | null | undefined,
  entities: Iterable<N>
): (query: { queryKey: QueryKey }) => boolean {
  const definitions = [...entities].map((name) => map[name]).filter(Boolean);
  return (query) =>
    definitions.some((definition) => queryBelongsTo(definition, orgId, query.queryKey));
}

const ORG_ENDPOINT = /^\/organizations\/([^/?#]+)\/([^/?#]+)/;

/** Resolve o endpoint de um CRUD (`/organizations/1/vehicles`) para a entidade da tabela. */
export function entityOfEndpoint<N extends string>(
  map: EntityMap<N>,
  endpoint: string
): { orgId: string | null; entity: N } | null {
  const match = ORG_ENDPOINT.exec(endpoint);
  const orgId = match ? match[1] : null;
  for (const name of Object.keys(map) as N[]) {
    const definition = map[name];
    if (match && (definition.orgPaths ?? []).includes(match[2])) return { orgId, entity: name };
    const bare = endpoint.replace(/^\//, "");
    if ((definition.keys ?? []).some((key) => isPathOrSubpath(bare, key.replace(/^\//, "")))) {
      return { orgId, entity: name };
    }
  }
  return null;
}
