import { ChatCircleIcon, LightningIcon, PlusIcon, RobotIcon, TrashIcon } from "@phosphor-icons/react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
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
import { deleteThread, fetchAgents, fetchThreads, type AgentModel, type Thread } from "@/lib/api";

export function AppSidebar() {
  const [agents, setAgents] = useState<AgentModel[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      const [agentsData, threadsData] = await Promise.all([fetchAgents(), fetchThreads()]);
      setAgents(agentsData);
      setThreads(threadsData);
    } catch (err) {
      console.error("Failed to load sidebar data:", err);
    } finally {
      setLoading(false);
    }
  }

  const chatAgents = agents.filter((a) => a.mode === "chat");
  const singleShotAgents = agents.filter((a) => a.mode === "single-shot");

  function handleNewChat(agentId: string) {
    const sessionId = `${agentId}_${crypto.randomUUID().slice(0, 8)}`;
    navigate({
      to: "/chat/$agentId",
      params: { agentId },
      search: { session: sessionId }
    });
  }

  async function handleDeleteThread(threadId: string) {
    try {
      await deleteThread(threadId);
      setThreads((prev) => prev.filter((t) => t.thread_id !== threadId));
    } catch (err) {
      console.error("Failed to delete thread:", err);
    }
  }

  return (
    <Sidebar>
      <SidebarHeader className="p-4">
        <div className="flex items-center gap-2">
          <RobotIcon className="size-6 text-primary" weight="duotone" />
          <span className="text-lg font-semibold">Agents</span>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <ScrollArea className="flex-1">
          {/* Chat Agents */}
          {chatAgents.length > 0 && (
            <SidebarGroup>
              <SidebarGroupLabel className="flex items-center gap-1.5">
                <ChatCircleIcon className="size-4" weight="duotone" />
                Chat
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {chatAgents.map((agent) => (
                    <div key={agent.id}>
                      <SidebarMenuItem>
                        <SidebarMenuButton onClick={() => handleNewChat(agent.id)} tooltip={agent.description}>
                          <PlusIcon className="size-4" />
                          <span>{agent.name}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>

                      {/* Threads for this agent */}
                      {threads
                        .filter((t) => t.thread_id.startsWith(agent.id) || t.agent_id === agent.id)
                        .slice(0, 10)
                        .map((thread) => (
                          <SidebarMenuItem key={thread.thread_id}>
                            <SidebarMenuButton
                              isActive={currentPath.includes(thread.thread_id)}
                              onClick={() =>
                                navigate({
                                  to: "/chat/$agentId",
                                  params: { agentId: agent.id },
                                  search: { session: thread.thread_id }
                                })
                              }
                              className="pl-8"
                            >
                              <span className="truncate text-sm text-muted-foreground">{thread.preview || "New conversation"}</span>
                            </SidebarMenuButton>
                            <SidebarMenuAction onClick={() => handleDeleteThread(thread.thread_id)}>
                              <TrashIcon className="size-3.5" />
                            </SidebarMenuAction>
                          </SidebarMenuItem>
                        ))}
                    </div>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}

          {chatAgents.length > 0 && singleShotAgents.length > 0 && <Separator className="my-2" />}

          {/* Single-shot Agents */}
          {singleShotAgents.length > 0 && (
            <SidebarGroup>
              <SidebarGroupLabel className="flex items-center gap-1.5">
                <LightningIcon className="size-4" weight="duotone" />
                Single-shot
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {singleShotAgents.map((agent) => (
                    <SidebarMenuItem key={agent.id}>
                      <SidebarMenuButton
                        isActive={currentPath.includes(agent.id)}
                        onClick={() =>
                          navigate({
                            to: "/agent/$agentId",
                            params: { agentId: agent.id }
                          })
                        }
                        tooltip={agent.description}
                      >
                        <LightningIcon className="size-4" />
                        <span>{agent.name}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}

          {loading && <div className="p-4 text-sm text-muted-foreground">Loading agents...</div>}
        </ScrollArea>
      </SidebarContent>

      <SidebarFooter className="p-3">
        <Button variant="outline" size="sm" className="w-full" onClick={loadData}>
          Refresh
        </Button>
      </SidebarFooter>
    </Sidebar>
  );
}
