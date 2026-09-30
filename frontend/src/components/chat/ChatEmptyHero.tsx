import { useAttachAndSend } from "@/components/chat/use-attach-and-send";
import { usePromptInputController } from "@/components/ai-elements/prompt-input";
import type { AgentSuggestion, AgentSuggestionInstant } from "@/lib/api";
import { motion } from "motion/react";
import { useMemo } from "react";

const MAX_HERO_SUGGESTIONS = 6;

interface ChatEmptyHeroProps {
  agentName: string | undefined;
  suggestions: AgentSuggestion[];
}

function isInstantDirect(s: AgentSuggestion): s is AgentSuggestionInstant {
  return s.kind === "instant" && s.section === "direct";
}

export function ChatEmptyHero({ agentName, suggestions }: ChatEmptyHeroProps) {
  const { textInput } = usePromptInputController();
  const attachAndSend = useAttachAndSend();

  const directSuggestions = useMemo(
    () => suggestions.filter(isInstantDirect).slice(0, MAX_HERO_SUGGESTIONS),
    [suggestions]
  );

  const heading = agentName ? `How can I help with ${agentName}?` : "How can I help?";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="mx-auto flex w-full max-w-3xl flex-col items-center gap-10 px-4 py-16 text-center"
    >
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{heading}</h1>

      {directSuggestions.length > 0 && (
        <div className="flex w-full flex-wrap justify-center gap-2">
          {directSuggestions.map((suggestion, i) => (
            <motion.button
              key={`${suggestion.label}-${i}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: 0.05 + i * 0.04, ease: "easeOut" }}
              type="button"
              onClick={() =>
                suggestion.action === "attach"
                  ? attachAndSend(suggestion.prompt)
                  : textInput.setInput(suggestion.prompt)
              }
              className="border-border/70 hover:bg-accent hover:border-border text-muted-foreground hover:text-foreground rounded-full border px-3.5 py-1.5 text-sm transition-colors"
            >
              {suggestion.label}
            </motion.button>
          ))}
        </div>
      )}
    </motion.div>
  );
}
