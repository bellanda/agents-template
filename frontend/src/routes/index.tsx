import { ChatCircleIcon, LightningIcon, RobotIcon, SparkleIcon } from "@phosphor-icons/react";
import { createFileRoute, Link } from "@tanstack/react-router";

import { SidebarLayout } from "@/components/layouts";

export const Route = createFileRoute("/")({ component: HomePage });

function HomePage() {
  return (
    <SidebarLayout>
      <div className="flex h-full flex-col items-center justify-center gap-6 p-8">
        <RobotIcon className="text-primary size-16" weight="duotone" />
        <h1 className="text-3xl font-bold">Agents Template</h1>
        <p className="text-muted-foreground max-w-md text-center">
          Select an agent from the sidebar to start. Agents with history enabled save conversation
          context across sessions.
        </p>
        <div className="mt-4 flex gap-6">
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <ChatCircleIcon className="text-primary size-5" weight="duotone" />
            <span>Chat = persistent conversation</span>
          </div>
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <LightningIcon className="text-primary size-5" weight="duotone" />
            <span>Single-shot = one-off request</span>
          </div>
        </div>
        <Link
          to="/react19-demo"
          className="bg-card hover:bg-accent mt-6 inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm transition-colors"
        >
          <SparkleIcon className="text-primary size-4" weight="duotone" />
          React 19 seed patterns (useActionState · useOptimistic · use)
        </Link>
      </div>
    </SidebarLayout>
  );
}
