// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import {
  CHATGPT_OPEN_DELAY_SECONDS,
  ChatGptLaunchDialog,
} from "@/components/agent-config/ChatGptLaunchDialog";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const PROMPT = "Monte as instruções da minha loja.";
const DELAY_MS = CHATGPT_OPEN_DELAY_SECONDS * 1000;

const openMock = vi.fn();
const writeText = vi.fn();
const onCloseSpy = vi.fn();

/** Mirrors the real parent (InstructionsCard): the dialog is mounted only while open. */
function Host({ copying }: { copying: Promise<void> }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <ChatGptLaunchDialog
      prompt={PROMPT}
      copying={copying}
      onClose={() => {
        onCloseSpy();
        setOpen(false);
      }}
    />
  );
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  openMock.mockReset().mockReturnValue({ opener: "x" });
  onCloseSpy.mockReset();
  writeText.mockReset().mockResolvedValue(undefined);
  vi.stubGlobal("open", openMock);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ChatGptLaunchDialog", () => {
  it("shows the copied state, counts down and opens chatgpt.com, then closes itself", async () => {
    render(<Host copying={Promise.resolve()} />);
    await advance(0);
    expect(screen.getByText("Prompt copiado")).toBeTruthy();
    expect(screen.getByText(/Abrindo o ChatGPT em 3 s/)).toBeTruthy();

    await advance(DELAY_MS - 1);
    expect(openMock).not.toHaveBeenCalled();
    await advance(1);
    expect(openMock).toHaveBeenCalledTimes(1);
    expect(openMock).toHaveBeenCalledWith("https://chatgpt.com/", "_blank");
    expect(onCloseSpy).toHaveBeenCalled();
  });

  it("never opens when the dialog is closed before the countdown ends", async () => {
    render(<Host copying={Promise.resolve()} />);
    await advance(0);
    await advance(1000);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await advance(DELAY_MS * 2);
    expect(onCloseSpy).toHaveBeenCalled();
    expect(openMock).not.toHaveBeenCalled();
  });

  it("falls back to a manual button when the popup is blocked", async () => {
    openMock.mockReturnValue(null);
    render(<Host copying={Promise.resolve()} />);
    await advance(0); // let the copy promise settle so the countdown starts
    await advance(DELAY_MS);
    expect(screen.getByText(/O navegador bloqueou a janela/)).toBeTruthy();
    expect(onCloseSpy).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Abrir o ChatGPT" }));
    expect(openMock).toHaveBeenCalledTimes(2);
  });

  it("shows the prompt when the clipboard fails and starts the countdown after a retry", async () => {
    const rejected = Promise.reject(new Error("denied"));
    rejected.catch(() => undefined); // the dialog handles it; this only avoids an unhandled-rejection warning
    render(<Host copying={rejected} />);
    await advance(DELAY_MS + 1000);
    expect(screen.getByText("Não consegui copiar automaticamente")).toBeTruthy();
    expect(screen.getByText(PROMPT)).toBeTruthy();
    expect(openMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Copiar de novo" }));
    await advance(0);
    expect(writeText).toHaveBeenCalledWith(PROMPT);
    expect(screen.getByText(/Abrindo o ChatGPT em 3 s/)).toBeTruthy();
    await advance(DELAY_MS);
    expect(openMock).toHaveBeenCalledWith("https://chatgpt.com/", "_blank");
  });
});
