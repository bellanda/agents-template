import { describe, expect, it } from "vitest";
import { createFakeApi, fakeApiError } from "@/test/fake-api";

// Autoteste do fake de API com memória (canônico da frota, shared-widgets, 2026-11-17).
const CONTACTS = "/organizations/:orgId/contacts";
const URL = "/organizations/org-1/contacts";

function seeded() {
  return createFakeApi({
    collections: {
      [CONTACTS]: [
        { id: 1, name: "Ana", phone: "5535900000001" },
        { id: 2, name: "Bia", phone: null },
      ],
    },
    routes: {
      "POST /organizations/:orgId/contacts/:id/merge": ({ params, body }) => ({
        mergedInto: params.id,
        body,
      }),
    },
  });
}

describe("fake-api", () => {
  it("guarda o que a tela grava: o GET seguinte devolve o valor novo", async () => {
    const api = seeded();

    const created = await api.client.post(URL, { name: "Caio", phone: "" });
    await api.client.patch(`${URL}/1`, { phone: "5535911112222" });
    await api.client.put(`${URL}/2`, { name: "Beatriz" });
    await api.client.delete(`${URL}/1`);
    const list = await api.client.get(URL);

    expect(created).toMatchObject({ status: 201, data: { id: 3, name: "Caio" } });
    expect(list.data).toEqual({
      items: [
        { id: 2, name: "Beatriz" },
        { id: 3, name: "Caio", phone: "" },
      ],
      total: 2,
      skip: 0,
      limit: 50,
      hasMore: false,
    });
    await expect(api.client.get(`${URL}/1`)).rejects.toMatchObject({ status: 404 });
    expect(api.bodyOf("PATCH", "/contacts/1")).toEqual({ phone: "5535911112222" });
    expect(api.countOf("DELETE", "/contacts/")).toBe(1);
  });

  it("pagina pela query, da URL ou de config.params", async () => {
    const api = seeded();

    const page = await api.client.get(`${URL}?skip=1`, { params: { limit: 1 } });

    expect(page.data).toMatchObject({ items: [{ id: 2 }], total: 2, hasMore: false });
  });

  it("PUT, PATCH e DELETE também levam config.params para a query da rota", async () => {
    const seen: Array<Record<string, string>> = [];
    const api = createFakeApi({
      routes: {
        "DELETE /docs/:id": ({ query }) => (seen.push(Object.fromEntries(query)), {}),
        "PATCH /docs/:id": ({ query }) => (seen.push(Object.fromEntries(query)), {}),
        "PUT /docs/:id": ({ query }) => (seen.push(Object.fromEntries(query)), {}),
      },
    });

    await api.client.delete("/docs/1", { params: { reason: "assinado errado" } });
    await api.client.patch("/docs/1", {}, { params: { force: "1" } });
    await api.client.put("/docs/1", {}, { params: { force: "1" } });

    expect(seen).toEqual([{ reason: "assinado errado" }, { force: "1" }, { force: "1" }]);
  });

  it("rota própria vence a coleção e recebe os parâmetros do caminho", async () => {
    const api = seeded();

    const merged = await api.client.post(`${URL}/2/merge`, { from: 1 });

    expect(merged.data).toEqual({ mergedInto: "2", body: { from: 1 } });
    expect(api.rows(CONTACTS)).toHaveLength(2);
  });

  it("falha planejada vale só para as próximas N chamadas e não grava nada", async () => {
    const api = seeded();
    api.fail(
      "PATCH /organizations/:orgId/contacts/:id",
      fakeApiError(409, "Conflito", { code: "X" })
    );

    const refused = api.client.patch(`${URL}/1`, { name: "Outra" });
    await expect(refused).rejects.toEqual({
      message: "Conflito",
      status: 409,
      code: "X",
      details: { code: "X" },
    });
    expect(api.rows(CONTACTS)[0].name).toBe("Ana");
    await api.client.patch(`${URL}/1`, { name: "Outra" });
    expect(api.rows(CONTACTS)[0].name).toBe("Outra");
  });

  it("a tela nunca segura a linha do fake: mutar a resposta não muda o próximo GET", async () => {
    const api = createFakeApi({
      collections: { [CONTACTS]: [{ id: 1, name: "Ana" }] },
      routes: { "GET /organizations/:orgId/summary": { total: 1 } },
    });

    const item = await api.client.get(`${URL}/1`);
    (item.data as { name: string }).name = "mutado na tela";
    const summary = await api.client.get("/organizations/org-1/summary");
    (summary.data as { total: number }).total = 99;

    expect((await api.client.get(`${URL}/1`)).data).toEqual({ id: 1, name: "Ana" });
    expect((await api.client.get("/organizations/org-1/summary")).data).toEqual({ total: 1 });
  });

  it("rota sem dono falha alto", async () => {
    const api = seeded();

    await expect(api.client.get("/organizations/org-1/nada")).rejects.toThrow(
      "fake-api: GET /organizations/org-1/nada não mapeado"
    );
  });
});
