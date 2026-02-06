import { ChatCircleIcon, LightningIcon, RobotIcon } from "@phosphor-icons/react";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({ component: HomePage });

function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
      <RobotIcon className="size-16 text-primary" weight="duotone" />
      <h1 className="text-3xl font-bold">Agents Template</h1>
      <p className="text-muted-foreground text-center max-w-md">
        Select an agent from the sidebar to start. Chat agents maintain conversation history, while single-shot agents handle one
        request at a time.
      </p>
      <div className="flex gap-6 mt-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <ChatCircleIcon className="size-5 text-primary" weight="duotone" />
          <span>Chat = persistent conversation</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <LightningIcon className="size-5 text-primary" weight="duotone" />
          <span>Single-shot = one-off request</span>
        </div>
      </div>
    </div>
  );
}
