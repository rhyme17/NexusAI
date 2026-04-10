import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Agent, Task } from "@/lib/api/types";
import { LanguageProvider } from "@/lib/i18n/language-context";

const useTasksMock = vi.hoisted(() => vi.fn());
const useAgentsMock = vi.hoisted(() => vi.fn());
const useBackendHealthMock = vi.hoisted(() => vi.fn());

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  )
}));

vi.mock("@/hooks/use-tasks", () => ({
  useTasks: useTasksMock
}));

vi.mock("@/hooks/use-agents", () => ({
  useAgents: useAgentsMock
}));

vi.mock("@/hooks/use-backend-health", () => ({
  useBackendHealth: useBackendHealthMock
}));

import { Dashboard } from "./dashboard";

function renderDashboard() {
  return render(
    <LanguageProvider>
      <Dashboard />
    </LanguageProvider>
  );
}

const tasksFixture: Task[] = [
  {
    task_id: "task_a",
    objective: "Plan a research workflow",
    priority: "high",
    status: "in_progress",
    progress: 35,
    assigned_agent_ids: ["agent_planner", "agent_research"],
    current_agent_id: "agent_planner",
    handoff_history: [],
    retry_count: 0,
    last_retry_at: null,
    proposals: [],
    consensus: null,
    result: null,
    metadata: {},
    created_at: "2026-04-05T10:00:00Z",
    updated_at: "2026-04-05T10:00:00Z"
  },
  {
    task_id: "task_b",
    objective: "Summarize findings",
    priority: "medium",
    status: "queued",
    progress: 0,
    assigned_agent_ids: ["agent_writer"],
    current_agent_id: null,
    handoff_history: [],
    retry_count: 0,
    last_retry_at: null,
    proposals: [],
    consensus: null,
    result: null,
    metadata: {},
    created_at: "2026-04-05T11:00:00Z",
    updated_at: "2026-04-05T11:00:00Z"
  }
];

const agentFixture: Agent[] = [
  {
    agent_id: "agent_planner",
    name: "Planner",
    role: "planner",
    skills: ["planning"],
    status: "online",
    metadata: {},
    created_at: "2026-04-05T09:00:00Z"
  },
  {
    agent_id: "agent_writer",
    name: "Writer",
    role: "writer",
    skills: ["writing"],
    status: "busy",
    metadata: {},
    created_at: "2026-04-05T09:05:00Z"
  }
];

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useTasksMock.mockReturnValue({
      tasks: tasksFixture,
      isLoading: false,
      error: null,
      refresh: vi.fn().mockResolvedValue(undefined)
    });

    useAgentsMock.mockReturnValue({
      agents: agentFixture,
      isLoading: false,
      error: null,
      refresh: vi.fn().mockResolvedValue(undefined)
    });

    useBackendHealthMock.mockReturnValue({
      status: "online",
      readOnly: false,
      storageBackend: "json",
      refresh: vi.fn().mockResolvedValue(undefined)
    });
  });

  it("renders the overview page with spotlight task and recent-task navigation", () => {
    renderDashboard();

    expect(screen.getByText("当前焦点")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Plan a research workflow" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /前往任务台|Open tasks/i })).toHaveAttribute("href", "/tasks");
    expect(screen.getByRole("link", { name: /前往智能体页|Open agents/i })).toHaveAttribute("href", "/agents");
    expect(screen.getByRole("link", { name: /查看全部/i })).toHaveAttribute("href", "/tasks");
  });

  it("refreshes all overview data from the header action", async () => {
    const refreshTasks = vi.fn().mockResolvedValue(undefined);
    const refreshAgents = vi.fn().mockResolvedValue(undefined);
    const refreshHealth = vi.fn().mockResolvedValue(undefined);

    useTasksMock.mockReturnValue({
      tasks: tasksFixture,
      isLoading: false,
      error: null,
      refresh: refreshTasks
    });
    useAgentsMock.mockReturnValue({
      agents: agentFixture,
      isLoading: false,
      error: null,
      refresh: refreshAgents
    });
    useBackendHealthMock.mockReturnValue({
      status: "online",
      readOnly: false,
      storageBackend: "json",
      refresh: refreshHealth
    });

    renderDashboard();

    fireEvent.click(screen.getByRole("button", { name: /刷新全局/i }));

    await waitFor(() => {
      expect(refreshTasks).toHaveBeenCalledTimes(1);
      expect(refreshAgents).toHaveBeenCalledTimes(1);
      expect(refreshHealth).toHaveBeenCalledTimes(1);
    });
  });

  it("shows a calm empty state when no tasks exist", () => {
    useTasksMock.mockReturnValue({
      tasks: [],
      isLoading: false,
      error: null,
      refresh: vi.fn().mockResolvedValue(undefined)
    });

    renderDashboard();

    expect(screen.getByText("还没有任务，可以先创建一个任务。")).toBeInTheDocument();
    expect(screen.getByText("暂无任务，进入任务台即可开始。")).toBeInTheDocument();
  });

  it("renders a user-friendly backend connectivity message", () => {
    useTasksMock.mockReturnValue({
      tasks: [],
      isLoading: false,
      error: new Error("Failed to fetch"),
      refresh: vi.fn().mockResolvedValue(undefined)
    });

    renderDashboard();

    expect(screen.getByText(/无法连接后端服务/)).toBeInTheDocument();
  });

  it("shows a read-only maintenance banner when backend health reports maintenance mode", () => {
    useBackendHealthMock.mockReturnValue({
      status: "online",
      readOnly: true,
      storageBackend: "postgres",
      refresh: vi.fn().mockResolvedValue(undefined)
    });

    renderDashboard();

    expect(screen.getByText(/只读维护模式/)).toBeInTheDocument();
    expect(screen.getAllByText(/backend=postgres/).length).toBeGreaterThan(0);
  });
});





