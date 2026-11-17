// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { CurrencyInput } from "@/components/ui/currency-input";
import { parseMoney } from "@/lib/utils/currency";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

afterEach(cleanup);

function Harness({ onValue }: { onValue: (v: string | null) => void }) {
  const [value, setValue] = useState("");
  return (
    <>
      <CurrencyInput aria-label="valor" value={value} onChange={setValue} />
      <button type="button" onClick={() => onValue(parseMoney(value))}>
        enviar
      </button>
    </>
  );
}

describe("CurrencyInput", () => {
  it("drops letters, normalizes on blur and submits the right amount", () => {
    let sent: string | null = "unset";
    render(<Harness onValue={(v) => (sent = v)} />);
    const input = screen.getByLabelText("valor") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "1.500,00abc" } });
    expect(input.value).toBe("1.500,00");
    fireEvent.blur(input);
    expect(input.value).toBe("1500,00");
    expect(input.getAttribute("aria-invalid")).toBeNull();

    fireEvent.click(screen.getByText("enviar"));
    expect(sent).toBe("1500");
  });

  it("flags ambiguous input instead of reformatting it", () => {
    render(<Harness onValue={() => undefined} />);
    const input = screen.getByLabelText("valor") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "1,500.00" } });
    fireEvent.blur(input);
    expect(input.value).toBe("1,500.00");
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });

  it("lets the user clear a typed 0 and keeps the field empty", () => {
    render(<Harness onValue={() => undefined} />);
    const input = screen.getByLabelText("valor") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "0" } });
    expect(input.value).toBe("0");
    fireEvent.change(input, { target: { value: "" } });
    expect(input.value).toBe("");
    fireEvent.blur(input);
    expect(input.value).toBe("");
  });

  it("selects the whole content on focus (next frame, for iOS)", async () => {
    render(<CurrencyInput aria-label="valor" value="150,00" onChange={() => undefined} />);
    const input = screen.getByLabelText("valor") as HTMLInputElement;
    fireEvent.focus(input);
    await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
    expect([input.selectionStart, input.selectionEnd]).toEqual([0, 6]);
    expect(input.getAttribute("enterkeyhint")).toBe("done");
  });

  it("integer mode uses the numeric keyboard and drops separators", () => {
    function IntegerHarness() {
      const [value, setValue] = useState("");
      return <CurrencyInput aria-label="km" decimals={0} value={value} onChange={setValue} />;
    }
    render(<IntegerHarness />);
    const input = screen.getByLabelText("km") as HTMLInputElement;
    expect(input.getAttribute("inputmode")).toBe("numeric");
    fireEvent.change(input, { target: { value: "1.500,5" } });
    expect(input.value).toBe("15005");
  });
});
