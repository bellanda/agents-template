// @vitest-environment jsdom
import type { PagedResponse } from "@/lib/api/types";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCrud } from "./useCrud";

const { listMock, updateMock, deleteMock, createCrudService } = vi.hoisted(() => {
  const listMock = vi.fn();
  const updateMock = vi.fn();
  const deleteMock = vi.fn();
  return {
    listMock,
    updateMock,
    deleteMock,
    createCrudService: vi.fn(() => ({
      list: listMock,
      update: updateMock,
      delete: deleteMock,
    })),
  };
});

vi.mock("@/lib/api/context", () => ({ useDataProvider: () => ({ createCrudService }) }));

interface Row {
  id: string;
  name: string;
}
const ENDPOINT = "/things";
const PAGE: PagedResponse<Row> = {
  items: [
    { id: "1", name: "A" },
    { id: "2", name: "B" },
  ],
  total: 2,
  skip: 0,
  limit: 10,
  hasMore: false,
};

let queryClient: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function mount() {
  return renderHook(
    () => {
      const crud = useCrud<Row>(ENDPOINT);
      return { list: crud.useList(), update: crud.useUpdate(), remove: crud.useDelete() };
    },
    { wrapper }
  );
}

// template-gap-03: the shared CRUD hook (list error surfaces, cache surgery on update/delete).
describe("useCrud", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
    });
    listMock.mockResolvedValue(PAGE);
  });

  it("hands the caller the error instead of an empty page", async () => {
    const denied = { status: 403, message: "denied" };
    listMock.mockReset();
    listMock.mockRejectedValue(denied);
    const { result } = mount();
    await waitFor(() => expect(result.current.list.isError).toBe(true));
    expect(result.current.list.error).toBe(denied);
  });

  it("splices a deleted row out of the cached list and decrements the total", async () => {
    const { result } = mount();
    await waitFor(() => expect(result.current.list.data?.items).toHaveLength(2));
    deleteMock.mockResolvedValue({ data: null, status: 204, success: true });
    listMock.mockResolvedValue({ ...PAGE, items: [PAGE.items[1]], total: 1 });

    await act(async () => {
      await result.current.remove.mutateAsync({ id: "1" });
    });

    await waitFor(() => expect(result.current.list.data?.items.map((r) => r.id)).toEqual(["2"]));
    expect(result.current.list.data?.total).toBe(1);
  });

  it("replaces an edited row in place", async () => {
    const { result } = mount();
    await waitFor(() => expect(result.current.list.data?.items).toHaveLength(2));
    updateMock.mockResolvedValue({ data: { id: "2", name: "B2" }, status: 200, success: true });

    await act(async () => {
      await result.current.update.mutateAsync({ id: "2", data: { name: "B2" } });
    });

    await waitFor(() =>
      expect(result.current.list.data?.items[1]).toEqual({ id: "2", name: "B2" })
    );
    expect(result.current.list.data?.items).toHaveLength(2);
  });
});
