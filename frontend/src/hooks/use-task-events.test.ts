import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BusMessage, MessageType } from "@/lib/api/types";

const apiClientMock = vi.hoisted(() => ({
  listTaskEventsMeta: vi.fn()
}));

const subscribeTaskEventsMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", () => ({
  apiClient: apiClientMock
}));

vi.mock("@/lib/ws/task-events", () => ({
  subscribeTaskEvents: subscribeTaskEventsMock
}));

import { useTaskEvents } from "./use-task-events";

const baseEvent: BusMessage = {
  message_id: "msg_1",
  type: "TaskClaim",
  sender: "agent_planner",
  receiver: null,
  task_id: "task_1",
  payload: { agent_id: "agent_planner" },
  metadata: {},
  timestamp: "2026-04-05T10:00:00Z"
};

describe("useTaskEvents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads initial task events and derives insights", async () => {
    apiClientMock.listTaskEventsMeta.mockResolvedValue({
      total_count: 3,
      offset: 0,
      limit: 150,
      sort: "desc",
      has_more: false,
      next_cursor: null,
      items: [
        baseEvent,
        {
          ...baseEvent,
          message_id: "msg_2",
          type: "Decision",
          payload: { decided_by: "majority_vote", reason: "agreement" }
        },
        {
          ...baseEvent,
          message_id: "msg_3",
          type: "TaskFailed",
          payload: { error_code: "E_TIMEOUT", error_message: "timeout" }
        }
      ]
    });
    subscribeTaskEventsMock.mockImplementation(() => () => undefined);

    const filters: { types: MessageType[]; from: string; to: string } = { types: [], from: "", to: "" };
    const { result } = renderHook(() => useTaskEvents("task_1", filters));

    await waitFor(() => {
      expect(result.current.events).toHaveLength(3);
    });

    expect(apiClientMock.listTaskEventsMeta).toHaveBeenCalledWith("task_1", {
      types: [],
      from: undefined,
      to: undefined,
      limit: 150,
      sort: "desc",
      cursor: undefined
    });
    expect(result.current.insights.latestClaim?.message_id).toBe("msg_1");
    expect(result.current.insights.latestDecision?.message_id).toBe("msg_2");
    expect(result.current.insights.latestFailure?.message_id).toBe("msg_3");
  });

  it("appends websocket events that pass active filters", async () => {
    apiClientMock.listTaskEventsMeta.mockResolvedValue({
      total_count: 0,
      offset: 0,
      limit: 150,
      sort: "desc",
      has_more: false,
      next_cursor: null,
      items: []
    });

    let pushEvent: ((event: BusMessage) => void) | undefined;
    subscribeTaskEventsMock.mockImplementation((taskId, onMessage) => {
      pushEvent = onMessage;
      return () => undefined;
    });

    const filters: { types: MessageType[]; from: string; to: string } = {
      types: ["TaskHandoff"],
      from: "",
      to: ""
    };
    const { result } = renderHook(() => useTaskEvents("task_1", filters));

    await waitFor(() => {
      expect(subscribeTaskEventsMock).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(apiClientMock.listTaskEventsMeta).toHaveBeenCalledWith("task_1", {
        types: ["TaskHandoff"],
        from: undefined,
        to: undefined,
        limit: 150,
        sort: "desc",
        cursor: undefined
      });
      expect(result.current.events).toEqual([]);
    });

    act(() => {
      pushEvent?.({
        ...baseEvent,
        message_id: "msg_handoff",
        type: "TaskHandoff",
        payload: { from_agent_id: "agent_planner", to_agent_id: "agent_writer" }
      });
    });

    act(() => {
      pushEvent?.({
        ...baseEvent,
        message_id: "msg_update",
        type: "TaskUpdate",
        payload: { progress: 50 }
      });
    });

    await waitFor(() => {
      expect(result.current.events.map((event) => event.message_id)).toEqual(["msg_handoff"]);
      expect(result.current.connectionState).toBe("connected");
      expect(result.current.insights.handoffCount).toBe(1);
    });
  });

  it("does not recreate websocket subscription when only filters change", async () => {
    apiClientMock.listTaskEventsMeta.mockResolvedValue({
      total_count: 0,
      offset: 0,
      limit: 150,
      sort: "desc",
      has_more: false,
      next_cursor: null,
      items: []
    });

    subscribeTaskEventsMock.mockImplementation(() => () => undefined);

    const { rerender } = renderHook(
      ({ filters }) => useTaskEvents("task_1", filters),
      {
        initialProps: { filters: { types: [], from: "", to: "" } as { types: MessageType[]; from: string; to: string } }
      }
    );

    await waitFor(() => {
      expect(subscribeTaskEventsMock).toHaveBeenCalledTimes(1);
    });

    rerender({ filters: { types: ["TaskHandoff"], from: "", to: "" } });
    rerender({ filters: { types: ["TaskHandoff"], from: "2026-04-05T09:00:00Z", to: "" } });

    await waitFor(() => {
      expect(subscribeTaskEventsMock).toHaveBeenCalledTimes(1);
    });
  });
});






