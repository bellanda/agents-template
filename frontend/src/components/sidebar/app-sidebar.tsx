import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem
} from "@/components/ui/sidebar";
import { useUserId } from "@/hooks/useUserId";
import { deleteThread, fetchThreads, type Thread } from "@/lib/api";
import { PlusIcon, RobotIcon, TrashIcon } from "@phosphor-icons/react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";

export function AppSidebar() {
  const [userId] = useUserId();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const routerState = useRouterState();
  const searchParams = new URLSearchParams(routerState.location.search);
  const currentSession = searchParams.get("session") || undefined;

  useEffect(() => {
    void loadData();
  }, [userId]);

  useEffect(() => {
    const handleThreadsUpdated = () => {
      void loadData();
    };

    window.addEventListener("agents:threads:updated", handleThreadsUpdated);
    return () => {
      window.removeEventListener("agents:threads:updated", handleThreadsUpdated);
    };
  }, [userId]);

  async function loadData(): Promise<void> {
    try {
      const threadsData = await fetchThreads(undefined, userId);
      setThreads(threadsData);
    } catch (err) {
      console.error("Failed to load threads:", err);
    } finally {
      setLoading(false);
    }
  }

  function handleNewChat(): void {
    // Use last selected agent from localStorage, or default to web-search-agent
    const lastAgentId = localStorage.getItem("lastSelectedAgentId") || "web-search-agent";
    navigate({
      to: "/chat/$agentId",
      params: { agentId: lastAgentId },
      search: { session: `chat_${crypto.randomUUID().slice(0, 8)}` }
    });
  }

  async function handleDeleteThread(threadId: string, e: React.MouseEvent): Promise<void> {
    e.stopPropagation();
    try {
      await deleteThread(threadId);
      setThreads((prev) => prev.filter((t) => t.thread_id !== threadId));
      if (currentSession === threadId) {
        handleNewChat();
      }
    } catch (err) {
      console.error("Failed to delete thread:", err);
    }
  }

  function handleThreadClick(thread: Thread): void {
    navigate({
      to: "/chat/$agentId",
      params: { agentId: thread.agent_id || "web-search-agent" },
      search: { session: thread.thread_id }
    });
  }

  const groupedThreads = (() => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const thisWeek = new Date(today);
    thisWeek.setDate(thisWeek.getDate() - 7);

    const groups: { label: string; threads: Thread[] }[] = [
      { label: "Today", threads: [] },
      { label: "Yesterday", threads: [] },
      { label: "Previous 7 days", threads: [] },
      { label: "Older", threads: [] }
    ];

    threads.forEach((thread) => {
      const threadDate = thread.created_at ? new Date(thread.created_at) : new Date(0);
      if (threadDate >= today) {
        groups[0]!.threads.push(thread);
      } else if (threadDate >= yesterday) {
        groups[1]!.threads.push(thread);
      } else if (threadDate >= thisWeek) {
        groups[2]!.threads.push(thread);
      } else {
        groups[3]!.threads.push(thread);
      }
    });

    return groups.filter((g) => g.threads.length > 0);
  })();

  return (
    <Sidebar collapsible="icon" className="w-[16rem] shrink-0">
      <SidebarHeader className="p-4">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="gap-2 cursor-pointer">
              <div className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                <RobotIcon className="size-4" weight="duotone" />
              </div>
              <div className="flex flex-col gap-0.5 leading-none">
                <span className="text-sm font-semibold">Agents Template</span>
                <span className="text-muted-foreground text-xs">Chat Playground</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <ScrollArea className="flex-1">
          <div className="p-2">
            <Button onClick={handleNewChat} className="w-full" size="sm">
              <PlusIcon className="size-4 mr-2" />
              New Chat
            </Button>
          </div>

          {loading && <div className="p-4 text-sm text-muted-foreground">Loading...</div>}

          {!loading && threads.length === 0 && (
            <div className="p-4 text-sm text-muted-foreground text-center">No conversations yet. Start a new chat!</div>
          )}

          {!loading &&
            groupedThreads.map((group) => (
              <SidebarGroup key={group.label}>
                <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {group.threads.map((thread) => (
                      <SidebarMenuItem key={thread.thread_id} className="min-w-0">
                        <SidebarMenuButton
                          isActive={currentSession === thread.thread_id}
                          onClick={() => handleThreadClick(thread)}
                          className="w-full min-w-0 cursor-pointer"
                        >
                          <span className="block max-w-50 truncate text-sm">{thread.preview || "New conversation"}</span>
                        </SidebarMenuButton>
                        <SidebarMenuAction
                          onClick={(e) => void handleDeleteThread(thread.thread_id, e)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <TrashIcon className="size-3.5" />
                        </SidebarMenuAction>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            ))}
        </ScrollArea>
      </SidebarContent>

      <SidebarFooter className="p-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton className="h-10 items-center gap-2 rounded-none px-2">
              <div className="bg-muted flex size-7 items-center justify-center rounded-full text-xs font-medium">DU</div>
              <div className="flex flex-1 flex-col leading-tight">
                <span className="truncate text-xs font-medium">Default User</span>
                <span className="truncate text-[10px] text-muted-foreground">default@example.com</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
