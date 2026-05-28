import { useDeleteThreadMutation, useThreadsQuery } from "@/components/chat/use-threads-query";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
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
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useUserId } from "@/hooks/useUserId";
import { prefetchThreadMessages, type Thread } from "@/lib/api";
import { PlusIcon, RobotIcon, TrashIcon } from "@phosphor-icons/react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useCallback, useRef } from "react";

const DEFAULT_AGENT_ID = "web-search-agent";

export function AppSidebar() {
  const [userId] = useUserId();
  const navigate = useNavigate();
  const routerState = useRouterState();
  const searchParams = new URLSearchParams(routerState.location.search);
  const currentSession = searchParams.get("session") || undefined;

  const { data: threads = [], isLoading } = useThreadsQuery(userId);
  const deleteMutation = useDeleteThreadMutation(userId);

  const handleNewChat = useCallback((): void => {
    const lastAgentId = localStorage.getItem("lastSelectedAgentId") || DEFAULT_AGENT_ID;
    navigate({
      to: "/chat/$agentId",
      params: { agentId: lastAgentId },
      search: { session: `chat_${crypto.randomUUID().slice(0, 8)}` },
    });
  }, [navigate]);

  const handleDeleteThread = useCallback(
    (threadId: string): void => {
      deleteMutation.mutate(threadId);
      if (currentSession === threadId) {
        handleNewChat();
      }
    },
    [deleteMutation, currentSession, handleNewChat]
  );

  const prefetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleThreadHover = useCallback(
    (thread: Thread) => {
      prefetchTimerRef.current = setTimeout(() => {
        void prefetchThreadMessages(thread.thread_id, userId);
        prefetchTimerRef.current = null;
      }, 80);
    },
    [userId]
  );

  const handleThreadHoverEnd = useCallback(() => {
    if (prefetchTimerRef.current) {
      clearTimeout(prefetchTimerRef.current);
      prefetchTimerRef.current = null;
    }
  }, []);

  const handleThreadClick = useCallback(
    (thread: Thread): void => {
      navigate({
        to: "/chat/$agentId",
        params: { agentId: thread.agent_id || DEFAULT_AGENT_ID },
        search: { session: thread.thread_id },
      });
    },
    [navigate]
  );

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
      { label: "Older", threads: [] },
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
            <SidebarMenuButton size="lg" className="cursor-pointer gap-2">
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
              <PlusIcon className="mr-2 size-4" />
              New Chat
            </Button>
          </div>

          {isLoading && <div className="text-muted-foreground p-4 text-sm">Loading...</div>}

          {!isLoading && threads.length === 0 && (
            <div className="text-muted-foreground p-4 text-center text-sm">
              No conversations yet. Start a new chat!
            </div>
          )}

          {!isLoading &&
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
                          onMouseEnter={() => handleThreadHover(thread)}
                          onMouseLeave={handleThreadHoverEnd}
                          className="w-full min-w-0 cursor-pointer"
                        >
                          <span className="block max-w-50 truncate text-sm">
                            {thread.preview || "New conversation"}
                          </span>
                        </SidebarMenuButton>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <SidebarMenuAction
                              onClick={(e) => e.stopPropagation()}
                              aria-label="Delete conversation"
                              className="opacity-0 transition-opacity group-hover:opacity-100"
                            >
                              <TrashIcon className="size-3.5" />
                            </SidebarMenuAction>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
                              <AlertDialogDescription>
                                This action cannot be undone. The messages and any attached files
                                will be permanently removed.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleDeleteThread(thread.thread_id)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Delete
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
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
              <div className="bg-muted flex size-7 items-center justify-center rounded-full text-xs font-medium">
                DU
              </div>
              <div className="flex flex-1 flex-col leading-tight">
                <span className="truncate text-xs font-medium">Default User</span>
                <span className="text-muted-foreground truncate text-[10px]">
                  default@example.com
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
