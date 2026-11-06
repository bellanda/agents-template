import {
  CHATGPT_URL_BUDGET,
  chatGptLaunchPlan,
} from "@/components/agent-config/chatgpt-builder-prompt";
import { describe, expect, it } from "vitest";

describe("chatGptLaunchPlan", () => {
  it("opens the prefilled URL when the encoded link fits the budget", () => {
    const plan = chatGptLaunchPlan("Olá, monte as instruções.");
    expect(plan.mode).toBe("url");
    expect(plan.url).toBe(
      `https://chatgpt.com/?prompt=${encodeURIComponent("Olá, monte as instruções.")}`
    );
  });

  it("falls back to the clipboard (empty chat) when the encoded link exceeds the budget", () => {
    const prompt = "ç".repeat(CHATGPT_URL_BUDGET / 6 + 1);
    expect(chatGptLaunchPlan(prompt)).toEqual({
      mode: "clipboard",
      url: "https://chatgpt.com/",
      text: prompt,
    });
  });
});
