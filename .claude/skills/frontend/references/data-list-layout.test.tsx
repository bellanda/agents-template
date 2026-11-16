import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LuTrash2 } from "react-icons/lu";

import { DataList, type DataListColumn, type DataListProps } from "./data-list";

// Regression suite for the fleet audit 2026-11-13 (design-parity-01, kailos-v1-02, nexarena-v1-01,
// nexarena-v4-01, drift-frontend-01). Identical in every app: it only uses props common to all
// DataList variants. jsdom has no layout, so it asserts the responsive CONTRACT (container-query
// classes, which columns reach the card), not pixels; pixels are covered by `bun run qa:visual`.

interface Row {
  id: string;
  name: string;
  email: string;
  status: string;
  total: string;
}

const ROWS: Row[] = [
  { id: "1", name: "Ana", email: "ana@example.com", status: "Pago", total: "R$ 10,00" },
  { id: "2", name: "Bruno", email: "bruno@example.com", status: "Aberto", total: "R$ 20,00" },
];

const COLUMNS: DataListColumn<Row>[] = [
  { id: "name", header: "Nome", role: "primary", cell: (row) => row.name },
  { id: "email", header: "E-mail", role: "secondary", cell: (row) => row.email },
  { id: "status", header: "Status", role: "badge", cell: (row) => row.status },
  { id: "total", header: "Total", cell: (row) => row.total },
];

function listProps(overrides: Partial<DataListProps<Row>> = {}): DataListProps<Row> {
  return {
    items: ROWS,
    columns: COLUMNS,
    getRowId: (row) => row.id,
    isLoading: false,
    isFetching: false,
    total: ROWS.length,
    page: 1,
    pageSize: 20,
    pageCount: 1,
    onPageChange: vi.fn(),
    emptyTitle: "Nada cadastrado.",
    ...overrides,
  };
}

describe("DataList responsive contract", () => {
  it("switches table and cards by the list's own width, never by the viewport", () => {
    const { container } = render(<DataList {...listProps()} />);

    // The list declares itself the `main` container so `@3xl/main:` works even inside dialogs.
    expect(container.querySelector(".\\@container\\/main")).not.toBeNull();
    const tableBox = container
      .querySelector("table")!
      .closest("[data-slot='table-container']")!.parentElement!;
    expect(tableBox.className).toContain("@3xl/main:block");
    expect(tableBox.className).not.toMatch(/(^|\s)md:block/);

    const cardsBox = screen.getAllByText("Ana")[1]!.closest(".space-y-3")!;
    expect(cardsBox.className).toContain("@3xl/main:hidden");
    expect(cardsBox.className).not.toMatch(/(^|\s)md:hidden/);
  });

  it("shows every value column (Total, Status) in the card, never only in the table", () => {
    const { container } = render(<DataList {...listProps()} />);
    const cards = container.querySelector(".space-y-3.\\@3xl\\/main\\:hidden")!;

    expect(cards.textContent).toContain("R$ 10,00");
    expect(cards.textContent).toContain("Pago");
    expect(cards.textContent).toContain("ana@example.com");
  });

  it("wraps free-text cells but keeps value cells on one line", () => {
    const { container } = render(<DataList {...listProps()} />);
    const cells = container.querySelectorAll("tbody tr:first-child td");

    expect(cells[0]!.className).toContain("whitespace-normal");
    expect(cells[1]!.className).toContain("whitespace-normal");
    expect(cells[3]!.className).not.toContain("whitespace-normal");
  });

  it("keeps the card title readable next to a wide badge", () => {
    const { container } = render(<DataList {...listProps()} />);
    const badgeBox = container.querySelector(
      ".space-y-3.\\@3xl\\/main\\:hidden .max-w-\\[60\\%\\]"
    );

    expect(badgeBox).not.toBeNull();
    expect(badgeBox!.className).toContain("min-w-0");
  });

  it("lets the card's secondary line wrap to two lines instead of truncating to one", () => {
    const { container } = render(<DataList {...listProps()} />);
    const cards = container.querySelector(".space-y-3.\\@3xl\\/main\\:hidden")!;
    const secondary = [...cards.querySelectorAll("div")].find(
      (el) => el.textContent === "ana@example.com" && el.children.length === 0
    )!;

    // Free-text secondary lines (address, e-mail, notes) keep their second line; the title stays truncate.
    expect(secondary.className).toContain("line-clamp-2");
    expect(secondary.className).not.toContain("truncate");
  });

  it("sizes the grid variant by the list width instead of the viewport", () => {
    const { container } = render(<DataList {...listProps({ variant: "grid" })} />);
    const grid = container.querySelector(".grid.gap-4")!;

    expect(grid.className).toContain("auto-fill");
    expect(grid.className).not.toMatch(/(^|\s)(sm|xl):grid-cols/);
  });
});

describe("DataList shared behaviour", () => {
  it("shows the error block with retry only when there is nothing to show", () => {
    const refetch = vi.fn();
    const { rerender } = render(
      <DataList
        {...listProps({ items: [], total: 0, isError: true, error: new Error("x"), refetch })}
      />
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(refetch).toHaveBeenCalledTimes(1);

    // A failed background refetch must not wipe the rows already on screen.
    rerender(<DataList {...listProps({ isError: true, error: new Error("x"), refetch })} />);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getAllByText("Ana").length).toBeGreaterThan(0);
  });

  it("disables an action with its reason as title and does not fire it", () => {
    const onSelect = vi.fn();
    render(
      <DataList
        {...listProps({
          actions: [
            {
              id: "delete",
              label: "Excluir",
              icon: LuTrash2,
              onSelect,
              disabledReason: (row: Row) => (row.id === "1" ? "Já entregue" : undefined),
            },
          ],
        })}
      />
    );

    const [first] = screen.getAllByRole("button", { name: "Excluir" });
    expect((first as HTMLButtonElement).disabled).toBe(true);
    expect(first!.closest("span")!.getAttribute("title")).toBe("Já entregue");
    fireEvent.click(first!);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("selects rows without opening them", () => {
    const onToggle = vi.fn();
    const onRowClick = vi.fn();
    render(
      <DataList
        {...listProps({
          onRowClick,
          selection: { selectedIds: new Set<string>(), onToggle, label: (row: Row) => row.name },
        })}
      />
    );

    fireEvent.click(screen.getAllByRole("checkbox", { name: "Selecionar Ana" })[0]!);
    expect(onToggle).toHaveBeenCalledWith("1");
    expect(onRowClick).not.toHaveBeenCalled();
  });
});
