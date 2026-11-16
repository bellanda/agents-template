import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { ENTITY_DEPENDENCIES } from "../entity-dependencies";
import {
  type EntityDefinition,
  defineEntityMap,
  entitiesPredicate,
  entityClosure,
  entityOfEndpoint,
  queryBelongsTo,
} from "../entity-graph";
import {
  invalidateEndpointDependents,
  invalidateEntity,
  invalidateEntityDependents,
} from "../invalidation";

const MAP = defineEntityMap({
  vehicle: { orgPaths: ["vehicles"], dependents: ["dashboard", "finance"] },
  finance: { orgPaths: ["finance"], dependents: ["dashboard"] },
  dashboard: { orgPaths: ["dashboard"], dependents: ["vehicle"] }, // ciclo de propósito
  whatsapp: { keys: ["whatsapp"] },
  evaluation: { keys: ["/evaluations"] },
});

describe("entity-graph", () => {
  it("fecha os dependentes de forma transitiva e tolera ciclo", () => {
    expect([...entityClosure(MAP, "finance")].sort()).toEqual(["dashboard", "finance", "vehicle"]);
    expect([...entityClosure(MAP, "whatsapp")]).toEqual(["whatsapp"]);
  });

  it("casa chave por caminho de org (sub-rotas inclusas), sem confundir org nem prefixo parecido", () => {
    const vehicle = MAP.vehicle;
    expect(queryBelongsTo(vehicle, "1", ["/organizations/1/vehicles", "list"])).toBe(true);
    expect(queryBelongsTo(vehicle, "1", ["/organizations/1/vehicles/9/documents/overview"])).toBe(
      true
    );
    expect(queryBelongsTo(vehicle, "1", ["/organizations/2/vehicles"])).toBe(false);
    expect(queryBelongsTo(vehicle, "1", ["/organizations/1/vehicles-extra"])).toBe(false);
    // org desconhecida (CRUD global): casa em qualquer org
    expect(queryBelongsTo(vehicle, null, ["/organizations/9/vehicles"])).toBe(true);
  });

  it("casa chaves soltas com ou sem barra inicial", () => {
    expect(queryBelongsTo(MAP.whatsapp, "1", ["whatsapp", "inbox"])).toBe(true);
    expect(queryBelongsTo(MAP.evaluation, null, ["/evaluations", "list"])).toBe(true);
    expect(queryBelongsTo(MAP.evaluation, null, ["evaluations", 7])).toBe(true);
    expect(queryBelongsTo(MAP.evaluation, null, ["evaluations-other"])).toBe(false);
    expect(queryBelongsTo(MAP.evaluation, null, [{ not: "string" }])).toBe(false);
  });

  it("resolve o endpoint do CRUD para a entidade", () => {
    expect(entityOfEndpoint(MAP, "/organizations/5/vehicles")).toEqual({
      orgId: "5",
      entity: "vehicle",
    });
    expect(entityOfEndpoint(MAP, "/evaluations")).toEqual({ orgId: null, entity: "evaluation" });
    expect(entityOfEndpoint(MAP, "/organizations/5/unknown")).toBeNull();
  });

  it("predicado cobre só as entidades pedidas", () => {
    const predicate = entitiesPredicate(MAP, "1", ["finance"]);
    expect(predicate({ queryKey: ["/organizations/1/finance", "panel"] })).toBe(true);
    expect(predicate({ queryKey: ["/organizations/1/vehicles"] })).toBe(false);
  });
});

describe("tabela do app", () => {
  it("todo dependente referencia uma entidade existente", () => {
    const names = new Set(Object.keys(ENTITY_DEPENDENCIES));
    for (const [name, definition] of Object.entries(ENTITY_DEPENDENCIES)) {
      for (const dependent of (definition as EntityDefinition).dependents ?? []) {
        expect(names.has(dependent), `${name} -> ${dependent}`).toBe(true);
      }
    }
  });

  it("nenhuma chave/caminho é reivindicado por duas entidades (resolução de endpoint ambígua)", () => {
    const seen = new Map<string, string>();
    for (const [name, definition] of Object.entries(ENTITY_DEPENDENCIES)) {
      const { orgPaths = [], keys = [] } = definition as EntityDefinition;
      for (const token of [
        ...orgPaths.map((p) => `org:${p}`),
        ...keys.map((k) => `key:${k.replace(/^\//, "")}`),
      ]) {
        expect(seen.get(token), `${token} em ${name} e ${seen.get(token)}`).toBeUndefined();
        seen.set(token, name);
      }
    }
  });
});

describe("invalidateEntity (tabela do app)", () => {
  const entities = Object.keys(ENTITY_DEPENDENCIES) as (keyof typeof ENTITY_DEPENDENCIES)[];
  const [root] = entities;

  function seeded() {
    const client = new QueryClient();
    const definition = ENTITY_DEPENDENCIES[root] as EntityDefinition;
    const key: unknown[] = definition.orgPaths?.[0]
      ? [`/organizations/1/${definition.orgPaths[0]}`, "list"]
      : [definition.keys?.[0] ?? root, "list"];
    client.setQueryData(key, ["x"]);
    client.setQueryData(["sem-relacao-nenhuma"], ["y"]);
    return { client, key };
  }

  it("invalida a entidade e não toca em queries sem dono", async () => {
    const { client, key } = seeded();
    await invalidateEntity(client, "1", root);
    expect(client.getQueryState(key)?.isInvalidated).toBe(true);
    expect(client.getQueryState(["sem-relacao-nenhuma"])?.isInvalidated).toBe(false);
  });

  it("dependentes não invalidam a própria entidade", async () => {
    const { client, key } = seeded();
    await invalidateEntityDependents(client, "1", root);
    expect(client.getQueryState(key)?.isInvalidated).toBe(false);
  });

  it("endpoint fora da tabela é no-op", async () => {
    const { client, key } = seeded();
    await invalidateEndpointDependents(client, "/organizations/1/nao-existe");
    expect(client.getQueryState(key)?.isInvalidated).toBe(false);
  });
});

describe("tipagem", () => {
  it("dependente desconhecido não compila", () => {
    // @ts-expect-error "ghost" não existe na tabela
    defineEntityMap({ a: { dependents: ["ghost"] } });
  });
});
