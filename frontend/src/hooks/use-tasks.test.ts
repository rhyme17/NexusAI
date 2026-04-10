import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CreateTaskPayload, Task } from "@/lib/api/types";

const apiClientMock = vi.hoisted(() => ({
  listTasks: vi.fn(),
  createTask: vi.fn()
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: apiClientMock
}));

import { useTasks } from "./use-tasks";

const sampleTask: Task = {
  task_id: "task_1",
  objective: "Research agent collaboration",
  priority: "high",
  status: "queued",
  progress: 0,
  assigned_agent_ids: ["agent_planner"],
  current_agent_id: null,
  handoff_history: [],
  retry_count: 0,
  last_retry_at: null,
  proposals: [],
  consensus: null,
  result: null,
  metadata: {},
  created_at: "2026-04-05T10:00:00Z",
  updated_at: "2026-04-05T10:00:00Z"
};

describe("useTasks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads tasks on mount", async () => {
    apiClientMock.listTasks.mockResolvedValue([sampleTask]);

    const { result } = renderHook(() => useTasks());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.tasks).toEqual([sampleTask]);
    expect(result.current.error).toBeNull();
    expect(apiClientMock.listTasks).toHaveBeenCalledTimes(1);
  });

  it("prepends a newly created task", async () => {
    apiClientMock.listTasks.mockResolvedValue([]);
    const createdTask: Task = {
      ...sampleTask,
      task_id: "task_2",
      objective: "Create frontend baseline"
    };
    apiClientMock.createTask.mockResolvedValue(createdTask);

    const { result } = renderHook(() => useTasks());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.createTask({
        objective: "Create frontend baseline",
        priority: "medium"
      } satisfies CreateTaskPayload);
    });

    expect(result.current.tasks[0]).toEqual(createdTask);
    expect(apiClientMock.createTask).toHaveBeenCalledWith({
      objective: "Create frontend baseline",
      priority: "medium"
    });
  });

  it("upserts an existing task in place", async () => {
    apiClientMock.listTasks.mockResolvedValue([sampleTask]);

    const { result } = renderHook(() => useTasks());

    await waitFor(() => {
      expect(result.current.tasks).toHaveLength(1);
    });

    act(() => {
      result.current.upsertTask({
        ...sampleTask,
        status: "completed",
        progress: 100,
        result: { summary: "done" },
        updated_at: "2026-04-05T10:30:00Z"
      });
    });

    expect(result.current.tasks).toHaveLength(1);
    expect(result.current.tasks[0]).toMatchObject({
      status: "completed",
      progress: 100,
      result: { summary: "done" }
    });
  });
});

