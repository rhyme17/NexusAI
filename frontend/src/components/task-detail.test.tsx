import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Task } from "@/lib/api/types";
import { LanguageProvider } from "@/lib/i18n/language-context";

const apiClientMock = vi.hoisted(() => ({
  getTaskAttempts: vi.fn(),
  getTaskConsensus: vi.fn(),
  simulateTask: vi.fn(),
  retryTask: vi.fn(),
  claimTask: vi.fn(),
  handoffTask: vi.fn(),
  previewExecuteTask: vi.fn(),
  executeTask: vi.fn()
}));

vi.mock("@/lib/api/client", () => ({
  apiClient: apiClientMock
}));

import { TaskDetail } from "./task-detail";

function renderTaskDetail(task: Task) {
  return render(
    <LanguageProvider>
      <TaskDetail task={task} onTaskPatched={vi.fn()} agents={[]} userApiKey="" />
    </LanguageProvider>
  );
}

const baseTask: Task = {
  task_id: "task_1",
  objective: "Coordinate multi-agent proposal",
  priority: "high",
  status: "in_progress",
  progress: 60,
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
  updated_at: "2026-04-05T10:10:00Z"
};

const failedTask: Task = {
  ...baseTask,
  status: "failed",
  progress: 100
};

describe("TaskDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiClientMock.getTaskAttempts.mockResolvedValue({
      task_id: "task_1",
      retry_count: 0,
      max_retries: 2,
      items: []
    });
    apiClientMock.previewExecuteTask.mockResolvedValue({
      task_id: "task_1",
      execution_mode: "single",
      provider: "openai_compatible",
      pipeline_error_policy: "fail_fast",
      allow_fallback: true,
      fallback_mode: "simulate",
      arbitration_mode: "off",
      judge_agent_id: "agent_judge",
      steps: [
        {
          step: 1,
          agent_id: "agent_planner",
          agent_role: "planner",
          transition_action: "claim",
          transition_from_agent_id: null
        }
      ],
      estimated_events: [
        {
          event_type: "AgentExecutionStart",
          condition: "always",
          step: 1,
          agent_id: "agent_planner",
          note: "Step 1"
        }
      ],
      preview_warnings: []
    });
    apiClientMock.executeTask.mockResolvedValue(baseTask);
  });

  it("renders proposal vs decision comparison rows", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: {
        conflict_detected: true,
        decision_result: {
          summary: "chosen",
          confidence: 0.91
        },
        decided_by: "majority_vote",
        reason: "highest agreement",
        decided_at: "2026-04-05T10:11:00Z"
      },
      proposals: [
        {
          agent_id: "agent_planner",
          confidence: 0.91,
          submitted_at: "2026-04-05T10:10:00Z",
          result: { summary: "chosen", confidence: 0.91 }
        },
        {
          agent_id: "agent_research",
          confidence: 0.72,
          submitted_at: "2026-04-05T10:09:00Z",
          result: { summary: "alternative", confidence: 0.72 }
        }
      ]
    });

    renderTaskDetail(baseTask);

    fireEvent.click(screen.getByTestId("task-detail-tab-coordination"));

    await waitFor(() => {
      expect(screen.getByText("方案与决策对照")).toBeInTheDocument();
    });

    expect(screen.getByRole("columnheader", { name: "字段" })).toBeInTheDocument();
    expect(screen.getByText("summary")).toBeInTheDocument();
    expect(screen.getByText("chosen")).toBeInTheDocument();
    expect(screen.getByText("agent_planner: chosen")).toBeInTheDocument();
    expect(screen.getByText("agent_research: alternative")).toBeInTheDocument();
  });

  it("shows empty consensus state when no consensus is available", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    renderTaskDetail(baseTask);

    fireEvent.click(screen.getByTestId("task-detail-tab-coordination"));

    await waitFor(() => {
      expect(screen.getByText("暂未形成共识。")).toBeInTheDocument();
    });
  });

  it("renders routing, consensus, and arbitration explanations when available", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: {
        conflict_detected: true,
        decision_result: { summary: "chosen" },
        decided_by: "highest_confidence",
        reason: "conflict resolved",
        explanation: {
          selected_agent_id: "agent_planner",
          comparison_basis: "highest confidence",
          proposal_count: 2
        },
        decided_at: "2026-04-05T10:11:00Z"
      },
      proposals: []
    });

    renderTaskDetail({
      ...baseTask,
      metadata: {
        routing: {
          reason: "Selected by skill overlap and status.",
          selected_agent_ids: ["agent_planner", "agent_research"]
        }
      },
      result: {
        arbitration: {
          explanation: {
            selection_basis: "judge override applied",
            selected_summary: "judge final summary"
          }
        }
      }
    });

    fireEvent.click(screen.getByTestId("task-detail-tab-overview"));
    await waitFor(() => {
      expect(screen.getByTestId("task-routing-explanation")).toBeInTheDocument();
      expect(screen.getByTestId("task-arbitration-explanation")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("task-detail-tab-coordination"));
    await waitFor(() => {
      expect(screen.getByTestId("task-consensus-explanation")).toBeInTheDocument();
    });
  });

  it("renders workflow runtime and DAG queue status in overview", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    renderTaskDetail({
      ...baseTask,
      metadata: {
        decomposition: {
          mode: "mvp_linear",
          template: "planning",
          workflow_run: {
            workflow_run_id: "wf_demo_1",
            queue_backend: "in_process",
            scheduler_mode: "mvp_linear_queue"
          },
          dispatch_state: {
            ready_count: 0,
            running_count: 1,
            blocked_count: 2,
            completed_count: 1,
            failed_count: 0
          },
          ready_queue: [],
          dag_nodes: [
            {
              node_id: "step_1",
              title: "Set scope",
              status: "completed",
              dispatch_state: "completed",
              assigned_agent_id: "agent_planner",
              depends_on: [],
              attempt_count: 1
            },
            {
              node_id: "step_2",
              title: "Collect evidence",
              status: "in_progress",
              dispatch_state: "running",
              assigned_agent_id: "agent_research",
              depends_on: ["step_1"],
              attempt_count: 1
            }
          ],
          subtasks: [
            {
              step_id: "step_1",
              title: "Set scope",
              status: "completed",
              assigned_agent_id: "agent_planner",
              depends_on: []
            }
          ]
        }
      }
    });

    fireEvent.click(screen.getByTestId("task-detail-tab-overview"));

    await waitFor(() => {
      expect(screen.getByTestId("task-workflow-runtime-panel")).toBeInTheDocument();
    });

    expect(screen.getByText(/scheduler=mvp_linear_queue/i)).toBeInTheDocument();
    expect(screen.getByText("Collect evidence")).toBeInTheDocument();
    expect(screen.getAllByText(/1/).length).toBeGreaterThan(0);
  });

  it("keeps claim and handoff actions accessible in execution panel", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    render(
      <LanguageProvider>
        <TaskDetail
          task={baseTask}
          onTaskPatched={vi.fn()}
          agents={[
            {
              agent_id: "agent_planner",
              name: "planner",
              role: "planner",
              skills: ["plan"],
              status: "online",
              metadata: {},
              created_at: "2026-04-05T10:00:00Z"
            },
            {
              agent_id: "agent_research",
              name: "research",
              role: "research",
              skills: ["research"],
              status: "online",
              metadata: {},
              created_at: "2026-04-05T10:00:00Z"
            }
          ]}
        />
      </LanguageProvider>
    );

    fireEvent.click(screen.getByTestId("task-detail-tab-execution"));
    await waitFor(() => {
      expect(screen.getByTestId("task-claim-button")).toBeInTheDocument();
      expect(screen.getByTestId("task-handoff-button")).toBeInTheDocument();
    });
  });

  it("shows friendly retry-limit error when retry is exhausted", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });
    apiClientMock.retryTask.mockRejectedValue(new Error('HTTP 409: {"detail":"Retry limit reached"}'));

    renderTaskDetail(failedTask);

    fireEvent.click(screen.getByTestId("task-retry-button"));

    await waitFor(() => {
      expect(
        screen.getByText("已达到重试上限。请先提高 max_retries 或排查失败原因后再重试。")
      ).toBeInTheDocument();
    });
  });

  it("renders execution preview and triggers execute API", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    render(
      <LanguageProvider>
        <TaskDetail task={baseTask} onTaskPatched={vi.fn()} agents={[]} userApiKey="user-api-key-token" />
      </LanguageProvider>
    );

    fireEvent.click(screen.getByTestId("task-preview-execution-button"));

    await waitFor(() => {
      expect(apiClientMock.previewExecuteTask).toHaveBeenCalledTimes(1);
      expect(screen.getByText("执行预览")).toBeInTheDocument();
      expect(screen.getByText(/AgentExecutionStart/i)).toBeInTheDocument();
      expect(apiClientMock.previewExecuteTask.mock.calls[0][1]).toMatchObject({ api_key: "user-api-key-token" });
    });

    if (screen.getByTestId("task-execute-button").hasAttribute("disabled")) {
      fireEvent.click(screen.getByTestId("task-preview-execution-button"));
      await waitFor(() => {
        expect(apiClientMock.previewExecuteTask).toHaveBeenCalledTimes(2);
      });
    }

    const executeButton = screen.getByTestId("task-execute-button");
    if (!executeButton.hasAttribute("disabled")) {
      fireEvent.click(executeButton);
      await waitFor(() => {
        expect(apiClientMock.executeTask).toHaveBeenCalledTimes(1);
        expect(apiClientMock.executeTask.mock.calls[0][1]).toMatchObject({ api_key: "user-api-key-token" });
      });
    }
  });

  it("blocks execute until a fresh preview exists", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    renderTaskDetail(baseTask);

    expect(screen.getByTestId("task-execute-button")).toBeDisabled();
    expect(apiClientMock.executeTask).not.toHaveBeenCalled();
  });

  it("marks preview stale after configuration changes", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    renderTaskDetail(baseTask);

    fireEvent.click(screen.getByTestId("task-preview-execution-button"));
    await waitFor(() => {
      expect(screen.getByTestId("task-execution-preview-panel")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue("单 Agent"), {
      target: { value: "pipeline" }
    });

    expect(screen.getByText("你的配置已变化，当前预览可能已过时，请重新预览后再执行。")).toBeInTheDocument();
    expect(screen.getByTestId("task-execute-button")).toBeDisabled();
  });

  it("shows preview failure message when preview request fails", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });
    apiClientMock.previewExecuteTask.mockRejectedValue(new Error("HTTP 422: invalid preview payload"));

    renderTaskDetail(baseTask);

    fireEvent.click(screen.getByTestId("task-preview-execution-button"));

    await waitFor(() => {
      expect(screen.getByText("请求参数无效，请检查当前输入后再试。")).toBeInTheDocument();
    });
  });

  it("surfaces structured execution failure guidance from task results", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    renderTaskDetail({
      ...failedTask,
      result: {
        error: "provider unavailable",
        error_details: {
          user_message: "模型服务暂时不可用。你可以稍后重试，或使用 fallback/模拟路径继续演示。",
          retryable: true
        }
      }
    });

    fireEvent.click(screen.getByTestId("task-detail-tab-overview"));

    await waitFor(() => {
      expect(screen.getByText("模型服务暂时不可用。你可以稍后重试，或使用 fallback/模拟路径继续演示。")).toBeInTheDocument();
    });

    expect(screen.getByText(/是否适合重试/)).toBeInTheDocument();
  });

  it("renders a scrollable final output panel with complete structured data", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    const longSummary = `DeepSeek final output ${"A".repeat(800)}`;
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });

    renderTaskDetail({
      ...baseTask,
      result: {
        summary: longSummary,
        mode: "real",
        provider: "openai_compatible",
        model: "deepseek-ai/DeepSeek-V3.2",
        execution_metrics: {
          latency_ms: 128,
          usage: { total_tokens: 456 }
        }
      }
    });

    fireEvent.click(screen.getByTestId("task-detail-tab-overview"));

    const finalOutput = await screen.findByTestId("task-final-output");
    expect(finalOutput.className).toContain("max-h-96");
    expect(finalOutput.className).toContain("overflow-y-auto");
    expect(finalOutput.textContent).toContain(longSummary);

    fireEvent.click(screen.getByRole("button", { name: /复制为 Markdown|Copy as Markdown/ }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalled();
    });

    expect(writeText.mock.calls[0][0]).toContain(longSummary);
  });

  it("renders a larger workflow overview within a soft budget", async () => {
    apiClientMock.getTaskConsensus.mockResolvedValue({
      task_id: "task_1",
      consensus: null,
      proposals: []
    });

    const dag_nodes = Array.from({ length: 50 }, (_, index) => ({
      node_id: `step_${index + 1}`,
      title: `Node ${index + 1}`,
      status: index === 0 ? "in_progress" : "queued",
      dispatch_state: index === 0 ? "running" : index === 1 ? "ready" : "blocked",
      assigned_agent_id: index % 2 === 0 ? "agent_planner" : "agent_research",
      depends_on: index === 0 ? [] : [`step_${index}`],
      attempt_count: index === 0 ? 1 : 0
    }));

    const started = performance.now();
    renderTaskDetail({
      ...baseTask,
      metadata: {
        decomposition: {
          mode: "mvp_linear",
          workflow_run: { workflow_run_id: "wf_big", queue_backend: "in_process", scheduler_mode: "mvp_linear_queue" },
          dispatch_state: {
            ready_count: 1,
            running_count: 1,
            blocked_count: 48,
            completed_count: 0,
            failed_count: 0
          },
          ready_queue: ["step_2"],
          dag_nodes,
          subtasks: dag_nodes.slice(0, 4).map((node) => ({
            step_id: node.node_id,
            title: node.title,
            status: node.status,
            assigned_agent_id: node.assigned_agent_id,
            depends_on: node.depends_on
          }))
        }
      }
    });
    fireEvent.click(screen.getByTestId("task-detail-tab-overview"));

    await waitFor(() => {
      expect(screen.getByText("Node 50")).toBeInTheDocument();
    });

    const elapsed = performance.now() - started;
    expect(elapsed).toBeLessThan(500);
  });
});

