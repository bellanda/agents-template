// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
/**
 * Tela de instruções do agente de ponta a ponta com o fake de API com memória (padrão da frota,
 * 2026-11-17, incidente QUB5J53): salvar -> a tela mostra o texto novo e a lista de versões ganha
 * a linha; restaurar -> o texto antigo vira a versão atual; erro -> o rascunho fica; sem permissão
 * -> sem botões. Nenhum hook é mockado: quem prova a atualização é o fake guardar a escrita e a
 * tela reler sozinha (`use-agent-config.ts` invalida a entidade `agentConfig`).
 */
import { AgentConfigScreen } from "@/components/agent-config/AgentConfigScreen";
import {
  makeCrudWorld,
  stubFetchFromFakeApi,
  type CrudWorld,
  makeCrudQueryClient,
} from "@/test/crud-world";
import { fakeApiError } from "@/test/fake-api";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

const AGENT = "assistant";

interface StoredVersion {
  version: number;
  model_id: string;
  system_prompt_markdown: string;
  note: string | null;
  created_by: string | null;
  created_at: string;
}

function makeBackend(initial: string[]) {
  const versions: StoredVersion[] = initial.map((markdown, index) => ({
    version: index + 1,
    model_id: "m",
    system_prompt_markdown: markdown,
    note: null,
    created_by: "default_user",
    created_at: "2026-11-01T12:00:00Z",
  }));
  let active = versions.length;
  const config = () => ({
    agent_id: AGENT,
    tenant_id: "t",
    model_id: "m",
    system_prompt_markdown:
      versions.find((row) => row.version === active)?.system_prompt_markdown ?? "",
    active_version: active,
    updated_at: null,
  });
  const bump = (markdown: string, note: string | null) => {
    active = versions.length + 1;
    versions.push({
      version: active,
      model_id: "m",
      system_prompt_markdown: markdown,
      note,
      created_by: "default_user",
      created_at: "2026-11-02T12:00:00Z",
    });
    return config();
  };
  return {
    "GET /agents": () => [{ id: AGENT, name: "Assistente" }],
    "GET /agents/:agentId/config": config,
    "GET /agents/:agentId/config/versions": () => ({ versions: [...versions].reverse() }),
    "PUT /agents/:agentId/config": ({ body }: { body: unknown }) => {
      const { system_prompt_markdown, note } = body as {
        system_prompt_markdown: string;
        note?: string;
      };
      return bump(system_prompt_markdown, note ?? null);
    },
    "POST /agents/:agentId/config/versions/:version/activate": ({
      params,
    }: {
      params: Record<string, string>;
    }) => {
      const source = versions.find((row) => row.version === Number(params.version));
      return bump(source?.system_prompt_markdown ?? "", null);
    },
  };
}

let api: CrudWorld["api"];

function mountScreen(canEdit = true) {
  render(
    <QueryClientProvider client={makeCrudQueryClient()}>
      <AgentConfigScreen agentId={AGENT} onAgentChange={() => {}} canEdit={canEdit} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  toast.success.mockClear();
  api = makeCrudWorld({ routes: makeBackend(["# Loja A", "# Loja B"]) }).api;
  stubFetchFromFakeApi(api);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function editAndSave(text: string, note?: string) {
  fireEvent.click(await screen.findByRole("button", { name: /Editar/ }));
  const textarea = (await screen.findByLabelText("Texto do ChatGPT")) as HTMLTextAreaElement;
  expect(textarea.value).toBe("# Loja B");
  fireEvent.change(textarea, { target: { value: text } });
  if (note) fireEvent.change(screen.getByLabelText(/Nota da versão/), { target: { value: note } });
  fireEvent.click(screen.getByRole("button", { name: /Salvar nova versão/ }));
}

describe("instruções do agente — CRUD de ponta a ponta", () => {
  it("lista: mostra o texto da versão atual e as versões salvas", async () => {
    mountScreen();
    expect(await screen.findByText("Loja B")).toBeTruthy();
    expect(await screen.findByText("v2")).toBeTruthy();
    expect(screen.getByText("v1")).toBeTruthy();
  });

  it("salvar: o PUT leva texto e nota, a tela mostra o novo e o histórico ganha a v3", async () => {
    mountScreen();
    await editAndSave("# Loja C", " nova rodada ");

    await waitFor(() => expect(toast.success).toHaveBeenCalled());
    expect(api.bodyOf("PUT", "/agents/assistant/config")).toEqual({
      system_prompt_markdown: "# Loja C",
      note: "nova rodada",
    });
    expect(await screen.findByText("Loja C")).toBeTruthy();
    expect(screen.queryByText("Loja B")).toBeNull();
    expect(await screen.findByText("v3")).toBeTruthy();
    expect(screen.getByText("nova rodada")).toBeTruthy();
  });

  it("restaurar: a v1 volta como v3 atual, o texto muda e a lista ganha a linha", async () => {
    mountScreen();
    await screen.findByText("v1");
    const row = screen.getByText("v1").closest("li") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Restaurar" }));

    expect(await screen.findByText("Loja A")).toBeTruthy();
    expect(await screen.findByText("v3")).toBeTruthy();
    expect(screen.queryByText("Loja B")).toBeNull();
    expect(api.countOf("POST", "/versions/1/activate")).toBe(1);
  });

  it("erro 409 ao salvar: o rascunho continua na tela e nada muda", async () => {
    mountScreen();
    api.fail("PUT /agents/:agentId/config", fakeApiError(409, "Conflito de versão."));
    await editAndSave("# Rascunho");

    await waitFor(() => expect(api.countOf("PUT", "/config")).toBe(1));
    const textarea = (await screen.findByLabelText("Texto do ChatGPT")) as HTMLTextAreaElement;
    expect(textarea.value).toBe("# Rascunho");
    expect(toast.success).not.toHaveBeenCalled();
    expect(screen.queryByText("v3")).toBeNull();
  });

  it("sem permissão de editar: não há Editar nem Restaurar", async () => {
    mountScreen(false);
    expect(await screen.findByText("Loja B")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Editar/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Restaurar" })).toBeNull();
  });
});
