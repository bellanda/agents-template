import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EntityPicker, type EntityPickerSource } from "./entity-picker";

interface Item {
  id: string;
  name: string;
}

const ITEMS: Item[] = [
  { id: "c1", name: "Ana" },
  { id: "c2", name: "Bruno" },
];

const fetchNextPage = vi.fn();

function source(items: Item[], total = items.length): EntityPickerSource<Item> {
  return {
    items,
    total,
    hasNextPage: items.length < total,
    isFetching: false,
    isFetchingNextPage: false,
    fetchNextPage,
  };
}

const useListMock = vi.fn((_params: { search?: string }, _options: { enabled: boolean }) =>
  source(ITEMS)
);
const onChange = vi.fn();
const onCreateNew = vi.fn();

function renderPicker(overrides: Record<string, unknown> = {}) {
  return render(
    <EntityPicker<Item>
      useList={useListMock}
      value={null}
      onChange={onChange}
      getId={(item) => item.id}
      getLabel={(item) => item.name}
      placeholder="Sem cliente"
      searchPlaceholder="Buscar cliente..."
      emptyText="Nenhum cliente encontrado."
      createLabel="Novo cliente…"
      onCreateNew={onCreateNew}
      {...overrides}
    />
  );
}

function openPicker() {
  fireEvent.click(screen.getByRole("combobox"));
}

describe("EntityPicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useListMock.mockImplementation(() => source(ITEMS));
    // jsdom não implementa nenhum dos dois; floating-ui (Popover) e cmdk exigem.
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      }
    );
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("only enables the server search when the popover opens", () => {
    renderPicker();
    expect(useListMock).toHaveBeenLastCalledWith(expect.anything(), { enabled: false });

    openPicker();
    expect(useListMock).toHaveBeenLastCalledWith({ search: undefined }, { enabled: true });
  });

  it("always opens below the field without flipping (2026-10-22 regression)", () => {
    renderPicker();
    openPicker();

    const content = screen.getByPlaceholderText("Buscar cliente...").closest("[data-side]");
    expect(content?.getAttribute("data-side")).toBe("bottom");
    expect(content?.className).toContain("max-h-(--radix-popover-content-available-height)");
  });

  it("shows loaded vs total in the fixed footer", () => {
    useListMock.mockImplementation(() => source(ITEMS, 1355));
    renderPicker();
    openPicker();

    expect(screen.getByText("2 de 1.355")).toBeTruthy();
    expect(screen.getByText("Carregar mais")).toBeTruthy();
  });

  it("drops the load-more sentinel once every item is loaded", () => {
    renderPicker();
    openPicker();

    expect(screen.queryByText("Carregar mais")).toBeNull();
  });

  it("searches on the server with the typed text", () => {
    renderPicker();
    openPicker();

    fireEvent.change(screen.getByPlaceholderText("Buscar cliente..."), {
      target: { value: "ana" },
    });
    expect(useListMock).toHaveBeenLastCalledWith({ search: "ana" }, { enabled: true });
  });

  it("selects an item, reports the full item and closes", () => {
    renderPicker();
    openPicker();
    fireEvent.click(screen.getByRole("option", { name: "Ana" }));

    expect(onChange).toHaveBeenCalledWith("c1", "Ana", ITEMS[0]);
    expect(screen.queryByRole("option")).toBeNull();
  });

  it("keeps the create CTA outside the scrolling list", () => {
    renderPicker();
    openPicker();
    expect(screen.queryByRole("option", { name: /Novo cliente/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Novo cliente/ }));

    expect(onCreateNew).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("option")).toBeNull();
  });

  it("keeps the create CTA visible on an empty result", () => {
    useListMock.mockImplementation(() => source([]));
    renderPicker();
    openPicker();

    expect(screen.getByText("Nenhum cliente encontrado.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Novo cliente/ }));
    expect(onCreateNew).toHaveBeenCalledTimes(1);
  });

  it("clears the selection via the X button", () => {
    renderPicker({ value: "c1", valueLabel: "Ana" });
    fireEvent.click(screen.getByRole("button", { name: "Limpar seleção" }));

    expect(onChange).toHaveBeenCalledWith(null, null, null);
  });

  it("hides the clear button and blocks the trigger when disabled", () => {
    renderPicker({ value: "c1", valueLabel: "Ana", disabled: true });

    expect(screen.queryByRole("button", { name: "Limpar seleção" })).toBeNull();
    expect(screen.getByRole("combobox")).toHaveProperty("disabled", true);
  });

  it("omits the create CTA when quick-create is not wired", () => {
    renderPicker({ createLabel: undefined, onCreateNew: undefined });
    openPicker();

    expect(screen.queryByRole("button", { name: /Novo/ })).toBeNull();
    expect(screen.getAllByRole("option")).toHaveLength(ITEMS.length);
  });
});
