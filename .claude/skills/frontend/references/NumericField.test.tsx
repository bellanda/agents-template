// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { NumericField } from "@/components/forms/NumericField";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

function Harness({
  onValue,
  initial = 0,
}: {
  onValue: (v: number | null) => void;
  initial?: number | null;
}) {
  const [value, setValue] = useState<number | null>(initial);
  return (
    <NumericField
      label="Meta"
      value={value}
      onChange={(next) => {
        setValue(next);
        onValue(next);
      }}
    />
  );
}

describe("NumericField", () => {
  it("renders label, value and hint trigger", () => {
    render(<NumericField label="Meta" hint="meta mensal" value={1500} onChange={() => {}} />);
    expect(screen.getByText("Meta")).toBeDefined();
    expect(screen.getByLabelText("Ajuda")).toBeDefined();
    expect(screen.getByDisplayValue("1500")).toBeDefined();
  });

  it("clearing the 0 leaves the field empty and emits null (never re-inserts 0)", () => {
    const onValue = vi.fn();
    render(<Harness onValue={onValue} />);
    const input = screen.getByDisplayValue("0") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "" } });
    expect(input.value).toBe("");
    expect(onValue).toHaveBeenLastCalledWith(null);
    fireEvent.change(input, { target: { value: "42" } });
    expect(input.value).toBe("42");
    expect(onValue).toHaveBeenLastCalledWith(42);
  });

  it("integer mode (default) rejects decimals; step 0.1 allows one decimal place", () => {
    const onInt = vi.fn();
    const { unmount } = render(<NumericField label="Dias" value={1} onChange={onInt} />);
    fireEvent.change(screen.getByDisplayValue("1"), { target: { value: "12,5" } });
    expect(onInt).toHaveBeenLastCalledWith(125);
    unmount();

    const onDec = vi.fn();
    render(<NumericField label="Pct" value={1} step={0.1} onChange={onDec} />);
    fireEvent.change(screen.getByDisplayValue("1"), { target: { value: "12,5" } });
    expect(onDec).toHaveBeenLastCalledWith(12.5);
  });

  it("parent that ignores null gets its value back on blur", () => {
    render(<NumericField label="Meta" value={5} onChange={() => {}} />);
    const input = screen.getByDisplayValue("5") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "" } });
    expect(input.value).toBe("");
    fireEvent.blur(input);
    expect(input.value).toBe("5");
  });
});
