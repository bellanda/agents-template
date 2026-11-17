// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
/**
 * Lista de conversas da sidebar com o fake de API com memória (padrão da frota, 2026-11-17):
 * a lista mostra o que o servidor tem; excluir pede confirmação e a conversa some; erro do
 * servidor devolve a conversa para a lista (a exclusão é otimista).
 */
import { AppSidebar } from "@/components/sidebar/app-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import {
  makeCrudWorld,
  stubFetchFromFakeApi,
  type CrudWorld,
  makeCrudQueryClient,
} from "@/test/crud-world";
import { fakeApiError, type FakeRow } from "@/test/fake-api";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.setConfig({ testTimeout: 30_000 });

function makeThread(id: string, preview: string): FakeRow {
  return {
    thread_id: id,
    agent_id: "assistant",
    preview,
    message_count: 2,
    created_at: new Date().toISOString(),
  };
}

let api: CrudWorld["api"];
let threads: FakeRow[];

beforeEach(() => {
  // jsdom não tem matchMedia; o SidebarProvider decide mobile/desktop por ele.
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia;
  threads = [makeThread("t1", "Quanto custa o plano?"), makeThread("t2", "Resumo da reunião")];
  api = makeCrudWorld({
    routes: {
      "GET /agents/threads": () => ({ threads }),
      "DELETE /agents/threads/:id": ({ params }) => {
        threads = threads.filter((thread) => thread.thread_id !== params.id);
        return null;
      },
    },
  }).api;
  stubFetchFromFakeApi(api);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function mountSidebar() {
  const rootRoute = createRootRoute({
    component: () => (
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    ),
  });
  const router = createRouter({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={makeCrudQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

async function deleteConversation(index: number) {
  fireEvent.click((await screen.findAllByRole("button", { name: "Delete conversation" }))[index]);
  fireEvent.click(
    within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete" })
  );
}

describe("conversas da sidebar — excluir de ponta a ponta", () => {
  it("lista as conversas do servidor e exclui a escolhida", async () => {
    await mountSidebar();
    expect(await screen.findByText("Quanto custa o plano?")).toBeTruthy();
    expect(screen.getByText("Resumo da reunião")).toBeTruthy();

    await deleteConversation(0);
    await waitFor(() => expect(api.countOf("DELETE", "/agents/threads/t1")).toBe(1));
    await waitFor(() => expect(screen.queryByText("Quanto custa o plano?")).toBeNull());
    expect(screen.getByText("Resumo da reunião")).toBeTruthy();
    expect(threads).toHaveLength(1);
  });

  it("erro do servidor: a conversa volta para a lista", async () => {
    await mountSidebar();
    await screen.findByText("Quanto custa o plano?");
    api.fail("DELETE /agents/threads/:id", fakeApiError(500, "Falha"));
    await deleteConversation(0);
    await waitFor(() => expect(api.countOf("DELETE", "/agents/threads/t1")).toBe(1));
    expect(await screen.findByText("Quanto custa o plano?")).toBeTruthy();
    expect(threads).toHaveLength(2);
  });
});
