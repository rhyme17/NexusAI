import type {
  Task,
  TaskConsensusResponse,
  TaskDagNode,
  TaskDecomposition,
  TaskDispatchState,
  TaskSubtask,
  TaskWorkflowRun
} from "@/lib/api/types";

export function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function toPrettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function getTaskResultErrorSummary(task: Task | null): { userMessage: string; retryable: boolean | null } | null {
  const result = task?.result;
  if (!result || typeof result !== "object") {
    return null;
  }

  const candidate = result as Record<string, unknown>;
  const errorDetails = candidate.error_details;
  if (errorDetails && typeof errorDetails === "object" && !Array.isArray(errorDetails)) {
    const detailsRecord = errorDetails as Record<string, unknown>;
    return {
      userMessage:
        typeof detailsRecord.user_message === "string"
          ? detailsRecord.user_message
          : typeof candidate.error === "string"
            ? candidate.error
            : "",
      retryable: typeof detailsRecord.retryable === "boolean" ? detailsRecord.retryable : null
    };
  }

  const fallbackError = candidate.fallback_error;
  if (fallbackError && typeof fallbackError === "object" && !Array.isArray(fallbackError)) {
    const fallbackRecord = fallbackError as Record<string, unknown>;
    return {
      userMessage:
        typeof fallbackRecord.user_message === "string"
          ? fallbackRecord.user_message
          : typeof candidate.fallback_reason === "string"
            ? candidate.fallback_reason
            : "",
      retryable: typeof fallbackRecord.retryable === "boolean" ? fallbackRecord.retryable : null
    };
  }

  return null;
}

export function buildConsensusComparisonRows(consensus: TaskConsensusResponse | null): ConsensusComparisonRow[] {
  if (!consensus || !consensus.consensus) {
    return [];
  }

  const decisionMap = toComparableRecord(consensus.consensus.decision_result);
  const proposalMaps = consensus.proposals.map((proposal) => ({
    agentId: proposal.agent_id,
    result: toComparableRecord(proposal.result)
  }));

  const allKeys = new Set<string>(Object.keys(decisionMap));
  proposalMaps.forEach((proposal) => {
    Object.keys(proposal.result).forEach((key) => allKeys.add(key));
  });

  return Array.from(allKeys)
    .sort((left, right) => left.localeCompare(right))
    .map((key) => {
      const decisionValue = stringifyComparableValue(decisionMap[key]);
      const proposalCells = proposalMaps.map((proposal) => {
        const value = stringifyComparableValue(proposal.result[key]);
        return {
          agentId: proposal.agentId,
          value,
          matchesDecision: value === decisionValue
        };
      });

      return {
        key,
        decisionValue,
        proposals: proposalCells
      };
    });
}

export function getRoutingExplanation(task: Task | null): { reason: string; selectedAgentIds: string[] } | null {
  const routing = task?.metadata?.routing;
  if (!routing || typeof routing !== "object" || Array.isArray(routing)) {
    return null;
  }
  const record = routing as Record<string, unknown>;
  const reason = typeof record.reason === "string" ? record.reason : "";
  const selectedAgentIds = Array.isArray(record.selected_agent_ids)
    ? record.selected_agent_ids.map((item) => String(item))
    : [];
  if (!reason && selectedAgentIds.length === 0) {
    return null;
  }
  return { reason: reason || "-", selectedAgentIds };
}

export function getConsensusExplanation(
  consensus: TaskConsensusResponse | null
): { summary: string; selectedAgentId: string | null } | null {
  const explanation = consensus?.consensus?.explanation;
  if (!explanation || typeof explanation !== "object" || Array.isArray(explanation)) {
    return null;
  }
  const record = explanation as Record<string, unknown>;
  const selectedAgentId = typeof record.selected_agent_id === "string" ? record.selected_agent_id : null;
  const comparisonBasis = typeof record.comparison_basis === "string" ? record.comparison_basis : null;
  const proposalCount = typeof record.proposal_count === "number" ? record.proposal_count : null;
  if (!selectedAgentId && !comparisonBasis && proposalCount === null) {
    return null;
  }
  const summaryParts = [comparisonBasis, proposalCount !== null ? `proposal_count=${proposalCount}` : null].filter(
    (item): item is string => Boolean(item)
  );
  return {
    summary: summaryParts.join(" • ") || "-",
    selectedAgentId
  };
}

export function getArbitrationExplanation(
  task: Task | null
): { selectionBasis: string; selectedSummary: string | null } | null {
  const arbitration = task?.result && typeof task.result === "object" ? (task.result as Record<string, unknown>).arbitration : null;
  if (!arbitration || typeof arbitration !== "object" || Array.isArray(arbitration)) {
    return null;
  }
  const arbitrationRecord = arbitration as Record<string, unknown>;
  const explanation = arbitrationRecord.explanation;
  if (!explanation || typeof explanation !== "object" || Array.isArray(explanation)) {
    return null;
  }
  const record = explanation as Record<string, unknown>;
  const selectionBasis = typeof record.selection_basis === "string" ? record.selection_basis : "-";
  const selectedSummary = typeof record.selected_summary === "string" ? record.selected_summary : null;
  return {
    selectionBasis,
    selectedSummary
  };
}

export function buildTaskResultExportContent(task: Task, format: "md" | "txt"): string {
  const result = task.result && typeof task.result === "object" ? task.result : {};
  const summary = getUserFacingResultContent(result);
  if (format === "txt") {
    return [
      `Task ID: ${task.task_id}`,
      `Objective: ${task.objective}`,
      `Status: ${task.status}`,
      `Updated: ${task.updated_at}`,
      "",
      "Result",
      "----------------------------------------",
      summary
    ].join("\n");
  }
  return [
    `# ${task.objective}`,
    "",
    `- Task ID: \`${task.task_id}\``,
    `- Status: \`${task.status}\``,
    `- Updated: \`${task.updated_at}\``,
    "",
    "## Result",
    "",
    summary
  ].join("\n");
}

export function getUserFacingResultContent(result: Record<string, unknown>): string {
  const directBody = ["final_output", "output", "report", "document", "content", "text", "summary"]
    .map((key) => result[key])
    .find((value) => typeof value === "string" && value.trim().length > 0);
  if (typeof directBody === "string") {
    return directBody;
  }
  return toPrettyJson(result);
}

export function getRetryErrorMessage(rawMessage: string): string {
  const normalized = rawMessage.toLowerCase();
  if (normalized.includes("retry limit reached")) {
    return "已达到重试上限。请先提高 max_retries 或排查失败原因后再重试。";
  }
  if (normalized.includes("only failed tasks can be retried")) {
    return "任务当前不是失败状态，仅失败任务可执行重试。";
  }
  return rawMessage;
}

export function getTaskDecomposition(task: Task | null): TaskDecomposition | null {
  const raw = task?.metadata?.decomposition;
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const candidate = raw as Partial<TaskDecomposition>;
  const subtaskRaw = Array.isArray(candidate.subtasks) ? candidate.subtasks : [];

  const subtasks: TaskSubtask[] = subtaskRaw
    .map((item) => {
      const step = item as Partial<TaskSubtask>;
      if (!step.step_id || !step.title) {
        return null;
      }

      return {
        step_id: String(step.step_id),
        title: String(step.title),
        status: typeof step.status === "string" ? step.status : "queued",
        assigned_agent_id:
          step.assigned_agent_id === null || step.assigned_agent_id === undefined
            ? null
            : String(step.assigned_agent_id),
        depends_on: Array.isArray(step.depends_on) ? step.depends_on.map((dependency) => String(dependency)) : []
      };
    })
    .filter((item): item is TaskSubtask => item !== null);

  const dagNodesRaw = Array.isArray((candidate as { dag_nodes?: unknown[] }).dag_nodes)
    ? ((candidate as { dag_nodes?: unknown[] }).dag_nodes ?? [])
    : [];
  const dagNodes = dagNodesRaw.reduce<TaskDagNode[]>((items, item) => {
    const node = item as Partial<TaskDagNode>;
    if (!node.node_id || !node.title) {
      return items;
    }
    items.push({
      node_id: String(node.node_id),
      title: String(node.title),
      status: typeof node.status === "string" ? node.status : "queued",
      dispatch_state: typeof node.dispatch_state === "string" ? node.dispatch_state : "blocked",
      assigned_agent_id:
        node.assigned_agent_id === null || node.assigned_agent_id === undefined ? null : String(node.assigned_agent_id),
      depends_on: Array.isArray(node.depends_on) ? node.depends_on.map((dependency) => String(dependency)) : [],
      sequence: typeof node.sequence === "number" ? node.sequence : undefined,
      attempt_count: typeof node.attempt_count === "number" ? node.attempt_count : undefined,
      started_at: typeof node.started_at === "string" ? node.started_at : undefined,
      completed_at: typeof node.completed_at === "string" ? node.completed_at : undefined,
      failed_at: typeof node.failed_at === "string" ? node.failed_at : undefined,
      last_error_code: typeof node.last_error_code === "string" ? node.last_error_code : undefined,
      last_error_message: typeof node.last_error_message === "string" ? node.last_error_message : undefined
    });
    return items;
  }, []);

  const workflowRun = readWorkflowRun(candidate);
  const dispatchState = readDispatchState(candidate);

  if (subtasks.length === 0 && dagNodes.length === 0) {
    return null;
  }

  const normalizedSubtasks =
    subtasks.length > 0
      ? subtasks
      : dagNodes.map<TaskSubtask>((node) => ({
          step_id: node.node_id,
          title: node.title,
          status: node.status,
          assigned_agent_id: node.assigned_agent_id,
          depends_on: node.depends_on,
        }));

  return {
    mode: typeof candidate.mode === "string" ? candidate.mode : "unknown",
    template: typeof candidate.template === "string" ? candidate.template : undefined,
    matched_keywords: Array.isArray(candidate.matched_keywords)
      ? candidate.matched_keywords.map((keyword) => String(keyword))
      : undefined,
    created_at: typeof candidate.created_at === "string" ? candidate.created_at : undefined,
    objective_snapshot: typeof candidate.objective_snapshot === "string" ? candidate.objective_snapshot : undefined,
    workflow_run: workflowRun,
    dag_nodes: dagNodes,
    ready_queue: Array.isArray((candidate as { ready_queue?: unknown[] }).ready_queue)
      ? ((candidate as { ready_queue?: unknown[] }).ready_queue ?? []).map((item) => String(item))
      : undefined,
    dispatch_state: dispatchState,
    subtasks: normalizedSubtasks
  };
}

function toComparableRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function stringifyComparableValue(value: unknown): string {
  if (value === undefined) {
    return "-";
  }
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function readWorkflowRun(candidate: Partial<TaskDecomposition>): TaskWorkflowRun | undefined {
  const raw = (candidate as { workflow_run?: unknown }).workflow_run;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return undefined;
  }
  const record = raw as Record<string, unknown>;
  return {
    workflow_run_id: typeof record.workflow_run_id === "string" ? record.workflow_run_id : undefined,
    queue_backend: typeof record.queue_backend === "string" ? record.queue_backend : undefined,
    scheduler_mode: typeof record.scheduler_mode === "string" ? record.scheduler_mode : undefined,
    node_count: typeof record.node_count === "number" ? record.node_count : undefined,
    edge_count: typeof record.edge_count === "number" ? record.edge_count : undefined
  };
}

function readDispatchState(candidate: Partial<TaskDecomposition>): TaskDispatchState | undefined {
  const raw = (candidate as { dispatch_state?: unknown }).dispatch_state;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return undefined;
  }
  const record = raw as Record<string, unknown>;
  return {
    pending_count: typeof record.pending_count === "number" ? record.pending_count : undefined,
    ready_count: typeof record.ready_count === "number" ? record.ready_count : undefined,
    blocked_count: typeof record.blocked_count === "number" ? record.blocked_count : undefined,
    running_count: typeof record.running_count === "number" ? record.running_count : undefined,
    completed_count: typeof record.completed_count === "number" ? record.completed_count : undefined,
    failed_count: typeof record.failed_count === "number" ? record.failed_count : undefined,
    last_transition_at: typeof record.last_transition_at === "string" ? record.last_transition_at : undefined
  };
}

interface ConsensusComparisonProposalCell {
  agentId: string;
  value: string;
  matchesDecision: boolean;
}

interface ConsensusComparisonRow {
  key: string;
  decisionValue: string;
  proposals: ConsensusComparisonProposalCell[];
}

