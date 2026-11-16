import type { QueryClient } from "@tanstack/react-query";
import { ENTITY_DEPENDENCIES } from "./entity-dependencies";
import { entitiesPredicate, entityClosure, entityOfEndpoint } from "./entity-graph";

/**
 * Invalidação por entidade (auditoria 2026-11-13, core-spa-02). Em vez de cada `onSuccess`
 * lembrar à mão quais telas dependem do que foi gravado, a mutation diz QUAL entidade mudou e
 * o mapa (`entity-dependencies.ts`, um por app) invalida ela e tudo que deriva dela.
 *
 * ```ts
 * onSuccess: () => invalidateEntity(queryClient, orgId, "serviceOrder")
 * // várias entidades de uma vez: invalidateEntity(queryClient, orgId, ["vehicle", "contact"])
 * ```
 *
 * Só queries ATIVAS refazem a request (as demais ficam velhas e refazem ao montar), então
 * declarar dependente demais custa pouco; esquecer um custa um número velho na tela.
 * `useCrud` já chama `invalidateEndpointDependents` em toda mutation.
 */
export type EntityName = Extract<keyof typeof ENTITY_DEPENDENCIES, string>;

interface InvalidateOptions {
  /** `none` só marca como velha (a aba que montar depois refaz); padrão `active`. */
  refetchType?: "active" | "none" | "all";
}

type OrgId = string | null | undefined;

function asList(entity: EntityName | readonly EntityName[]): readonly EntityName[] {
  return typeof entity === "string" ? [entity] : entity;
}

/** Invalida a(s) entidade(s) e todos os dependentes transitivos. */
export function invalidateEntity(
  queryClient: QueryClient,
  orgId: OrgId,
  entity: EntityName | readonly EntityName[],
  { refetchType = "active" }: InvalidateOptions = {}
): Promise<void> {
  const closure = new Set<EntityName>();
  for (const name of asList(entity)) {
    for (const reached of entityClosure(ENTITY_DEPENDENCIES, name)) closure.add(reached);
  }
  return queryClient.invalidateQueries({
    predicate: entitiesPredicate(ENTITY_DEPENDENCIES, orgId, closure),
    refetchType,
  });
}

/**
 * Só os DEPENDENTES, sem a própria entidade. Para quem já cuida das queries da entidade com
 * cirurgia de cache (`useCrud`: troca a linha no lugar) e só precisa avisar o resto.
 */
export function invalidateEntityDependents(
  queryClient: QueryClient,
  orgId: OrgId,
  entity: EntityName,
  { refetchType = "active" }: InvalidateOptions = {}
): Promise<void> {
  const closure = entityClosure(ENTITY_DEPENDENCIES, entity);
  closure.delete(entity);
  if (closure.size === 0) return Promise.resolve();
  return queryClient.invalidateQueries({
    predicate: entitiesPredicate(ENTITY_DEPENDENCIES, orgId, closure),
    refetchType,
  });
}

/**
 * Para o `useCrud`: resolve o endpoint do CRUD (`/organizations/1/vehicles`) para a entidade
 * da tabela e invalida os dependentes. Endpoint que não está na tabela: no-op.
 */
export function invalidateEndpointDependents(
  queryClient: QueryClient,
  endpoint: string
): Promise<void> {
  const resolved = entityOfEndpoint(ENTITY_DEPENDENCIES, endpoint);
  if (!resolved) return Promise.resolve();
  return invalidateEntityDependents(queryClient, resolved.orgId, resolved.entity);
}
