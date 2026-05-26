import {
	ChatCircleIcon,
	LightningIcon,
	RobotIcon,
	SparkleIcon,
} from "@phosphor-icons/react";
import { createFileRoute, Link } from "@tanstack/react-router";

import { SidebarLayout } from "@/components/layouts";

export const Route = createFileRoute("/")({ component: HomePage });

function HomePage() {
	return (
		<SidebarLayout>
			<div className="flex flex-col items-center justify-center h-full gap-6 p-8">
				<RobotIcon className="size-16 text-primary" weight="duotone" />
				<h1 className="text-3xl font-bold">Agents Template</h1>
				<p className="text-muted-foreground text-center max-w-md">
					Select an agent from the sidebar to start. Agents with history enabled
					save conversation context across sessions.
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
				<Link
					to="/react19-demo"
					className="mt-6 inline-flex items-center gap-2 rounded-md border bg-card px-4 py-2 text-sm hover:bg-accent transition-colors"
				>
					<SparkleIcon className="size-4 text-primary" weight="duotone" />
					React 19 seed patterns (useActionState · useOptimistic · use)
				</Link>
			</div>
		</SidebarLayout>
	);
}
