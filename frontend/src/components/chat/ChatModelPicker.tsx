import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorLogo,
  ModelSelectorLogoGroup,
  ModelSelectorName,
  ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector";
import { PromptInputButton } from "@/components/ai-elements/prompt-input";
import { enrichAgent } from "@/components/chat/use-agent-selection";
import type { AgentModel } from "@/lib/api";
import { CheckIcon } from "lucide-react";
import { memo, useCallback, useMemo } from "react";

const HIDDEN_LOGO_SLUGS = new Set(["zai"]);

interface ModelItemProps {
  agent: AgentModel;
  selectedAgentId: string;
  onSelect: (id: string) => void;
}

const ModelItem = memo(({ agent, selectedAgentId, onSelect }: ModelItemProps) => {
  const handleSelect = useCallback(() => onSelect(agent.id), [onSelect, agent.id]);
  const enriched = useMemo(() => enrichAgent(agent), [agent]);

  const chefSlug = enriched.chefSlug;
  const showChefLogo = chefSlug !== undefined && !HIDDEN_LOGO_SLUGS.has(chefSlug);

  return (
    <ModelSelectorItem onSelect={handleSelect} value={agent.id}>
      {showChefLogo && <ModelSelectorLogo provider={chefSlug} />}
      <ModelSelectorName>{agent.name}</ModelSelectorName>
      {enriched.providers && enriched.providers.length > 0 && (
        <ModelSelectorLogoGroup>
          {enriched.providers.map((p) => (
            <ModelSelectorLogo key={p} provider={p} />
          ))}
        </ModelSelectorLogoGroup>
      )}
      {selectedAgentId === agent.id ? (
        <CheckIcon className="ml-auto size-4" />
      ) : (
        <div className="ml-auto size-4" />
      )}
    </ModelSelectorItem>
  );
});
ModelItem.displayName = "ModelItem";

interface ChatModelPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedAgent: AgentModel | undefined;
  selectedAgentId: string;
  agentsByChef: Record<string, AgentModel[]>;
  onSelect: (id: string) => void;
}

export function ChatModelPicker({
  open,
  onOpenChange,
  selectedAgent,
  selectedAgentId,
  agentsByChef,
  onSelect,
}: ChatModelPickerProps) {
  const chefSlug = selectedAgent?.chefSlug;
  const showSelectedLogo = chefSlug !== undefined && !HIDDEN_LOGO_SLUGS.has(chefSlug);

  return (
    <ModelSelector open={open} onOpenChange={onOpenChange}>
      <ModelSelectorTrigger asChild>
        <PromptInputButton
          variant="ghost"
          className="h-9 gap-1.5 rounded-md px-2 text-sm font-medium [&_svg]:size-4.5"
        >
          {showSelectedLogo && <ModelSelectorLogo provider={chefSlug} className="size-4.5" />}
          {selectedAgent?.name && (
            <ModelSelectorName className="flex-none">{selectedAgent.name}</ModelSelectorName>
          )}
        </PromptInputButton>
      </ModelSelectorTrigger>
      <ModelSelectorContent>
        <ModelSelectorInput placeholder="Search agents..." />
        <ModelSelectorList>
          <ModelSelectorEmpty>No agents found.</ModelSelectorEmpty>
          {Object.entries(agentsByChef).map(([chef, chefAgents]) => (
            <ModelSelectorGroup heading={chef} key={chef}>
              {chefAgents.map((agent) => (
                <ModelItem
                  key={agent.id}
                  agent={agent}
                  onSelect={onSelect}
                  selectedAgentId={selectedAgentId}
                />
              ))}
            </ModelSelectorGroup>
          ))}
        </ModelSelectorList>
      </ModelSelectorContent>
    </ModelSelector>
  );
}
