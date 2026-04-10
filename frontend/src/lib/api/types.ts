export type TaskPriority = "low" | "medium" | "high";
export type TaskStatus = "queued" | "in_progress" | "completed" | "failed";

export type MessageType =
  | "TaskRequest"
  | "TaskClaim"
  | "TaskUpdate"
  | "TaskResult"
  | "TaskHandoff"
  | "TaskReject"
  | "TaskRetry"
  | "TaskRetryExhausted"
  | "Vote"
  | "ConflictNotice"
  | "Decision"
  | "TaskComplete"
  | "TaskFailed"
  | "TaskPipelineStart"
  | "TaskPipelineFinish"
  | "AgentExecutionStart"
  | "AgentExecutionResult"
  | "AgentExecutionError";

export const MESSAGE_TYPE_OPTIONS: MessageType[] = [
  "TaskRequest",
  "TaskClaim",
  "TaskUpdate",
  "TaskResult",
  "TaskHandoff",
  "TaskReject",
  "TaskRetry",
  "TaskRetryExhausted",
  "Vote",
  "ConflictNotice",
  "Decision",
  "TaskComplete",
  "TaskFailed",
  "TaskPipelineStart",
  "TaskPipelineFinish",
  "AgentExecutionStart",
  "AgentExecutionResult",
  "AgentExecutionError"
];

export type ExecutionMode = "single" | "pipeline" | "parallel";
export type PipelineErrorPolicy = "fail_fast" | "continue";
export type FallbackMode = "simulate" | "fail";
export type ArbitrationMode = "off" | "judge_on_conflict" | "judge_always";
export type TaskResultExportFormat = "md" | "txt";

export interface TaskExecutionRequest {
  agent_id?: string;
  execution_mode?: ExecutionMode;
  pipeline_agent_ids?: string[];
  pipeline_error_policy?: PipelineErrorPolicy;
  progress_points?: number[];
  provider?: "openai_compatible";
  api_key?: string;
  model?: string;
  system_instruction?: string;
  temperature?: number;
  max_tokens?: number;
  allow_fallback?: boolean;
  fallback_mode?: FallbackMode;
  arbitration_mode?: ArbitrationMode;
  judge_agent_id?: string;
}

export interface TaskExecutionPlanStep {
  step: number;
  agent_id: string;
  agent_role: string;
  transition_action: "claim" | "handoff" | "keep" | "parallel_dispatch";
  transition_from_agent_id: string | null;
}

export interface TaskExecutionPreviewEvent {
  event_type:
    | "TaskPipelineStart"
    | "AgentExecutionStart"
    | "AgentExecutionResult"
    | "AgentExecutionError"
    | "TaskPipelineFinish"
    | "TaskResult"
    | "TaskComplete"
    | "TaskFailed";
  condition: "always" | "on_error" | "on_fallback" | "on_no_fallback";
  step?: number | null;
  agent_id?: string | null;
  note?: string | null;
}

export interface TaskExecutionPreviewWarning {
  code: string;
  message: string;
  severity: "info" | "warning";
  applies_to_step?: number | null;
}

export interface TaskExecutionPreviewResponse {
  task_id: string;
  execution_mode: ExecutionMode;
  provider: "openai_compatible";
  pipeline_error_policy: PipelineErrorPolicy;
  allow_fallback: boolean;
  fallback_mode: FallbackMode;
  arbitration_mode: ArbitrationMode;
  judge_agent_id: string | null;
  steps: TaskExecutionPlanStep[];
  estimated_events: TaskExecutionPreviewEvent[];
  preview_warnings: TaskExecutionPreviewWarning[];
}

export interface TaskProposal {
  agent_id: string;
  result: Record<string, unknown>;
  confidence: number;
  submitted_at: string;
}

export interface TaskConsensus {
  conflict_detected: boolean;
  decision_result: Record<string, unknown>;
  decided_by: string;
  reason: string;
  explanation?: Record<string, unknown> | null;
  decided_at: string;
}

export interface TaskHandoffRecord {
  from_agent_id: string;
  to_agent_id: string;
  reason: string | null;
  handed_off_at: string;
}

export interface Agent {
  agent_id: string;
  name: string;
  role: string;
  skills: string[];
  status: "online" | "offline" | "busy";
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AgentRegisterPayload {
  name: string;
  role: string;
  skills: string[];
  metadata?: Record<string, unknown>;
}

export interface TaskAttemptRecord {
  attempt_number: number;
  outcome: "failed" | "retried" | "completed";
  reason: string | null;
  error_code: string | null;
  timestamp: string;
}

export type TaskSubtaskStatus = "queued" | "in_progress" | "completed" | "failed";

export interface TaskSubtask {
  step_id: string;
  title: string;
  status: TaskSubtaskStatus | string;
  assigned_agent_id: string | null;
  depends_on: string[];
}

export interface TaskDagNode {
  node_id: string;
  title: string;
  status: TaskSubtaskStatus | string;
  dispatch_state: "ready" | "blocked" | "running" | "completed" | "failed" | string;
  assigned_agent_id: string | null;
  depends_on: string[];
  sequence?: number;
  attempt_count?: number;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  last_error_code?: string | null;
  last_error_message?: string | null;
}

export interface TaskWorkflowRun {
  workflow_run_id?: string;
  queue_backend?: string;
  scheduler_mode?: string;
  node_count?: number;
  edge_count?: number;
}

export interface TaskDispatchState {
  pending_count?: number;
  ready_count?: number;
  blocked_count?: number;
  running_count?: number;
  completed_count?: number;
  failed_count?: number;
  last_transition_at?: string;
}

export interface TaskDecomposition {
  mode: string;
  template?: string;
  matched_keywords?: string[];
  created_at?: string;
  objective_snapshot?: string;
  workflow_run?: TaskWorkflowRun;
  dag_nodes?: TaskDagNode[];
  ready_queue?: string[];
  dispatch_state?: TaskDispatchState;
  subtasks: TaskSubtask[];
}

export interface Task {
  task_id: string;
  objective: string;
  priority: TaskPriority;
  status: TaskStatus;
  progress: number;
  assigned_agent_ids: string[];
  current_agent_id: string | null;
  handoff_history?: TaskHandoffRecord[];
  retry_count: number;
  last_retry_at: string | null;
  proposals?: TaskProposal[];
  consensus?: TaskConsensus | null;
  result: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TaskConsensusResponse {
  task_id: string;
  consensus: TaskConsensus | null;
  proposals: TaskProposal[];
}

export interface BusMessage {
  message_id: string;
  type: MessageType;
  sender: string;
  receiver: string | null;
  task_id: string | null;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
  timestamp: string;
}

export interface TaskAttemptsResponse {
  task_id: string;
  retry_count: number;
  max_retries: number;
  items: TaskAttemptRecord[];
}

export interface TaskEventsResponse {
  total_count: number;
  offset: number;
  limit: number;
  sort: "asc" | "desc";
  has_more: boolean;
  next_cursor: string | null;
  items: BusMessage[];
}

export interface CreateTaskPayload {
  objective: string;
  priority: TaskPriority;
  metadata?: Record<string, unknown>;
}

export interface HealthStatusResponse {
  status: string;
  read_only?: boolean;
  storage_backend?: string;
}

export type UserRole = "admin" | "operator" | "viewer";

export interface AuthUser {
  user_id: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface RegisterUserPayload {
  username: string;
  password: string;
  invite_code: string;
}

export interface LoginUserPayload {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
}

export interface DeleteOwnAccountResponse {
  status: string;
  deleted_tasks: number;
}

export interface InviteCode {
  code: string;
  created_by: string;
  max_uses: number;
  used_count: number;
  expires_at: string | null;
  created_at: string;
}

export interface CreateInvitePayload {
  code?: string;
  max_uses?: number;
  expires_hours?: number;
}

export interface UpdateUserStatusPayload {
  is_active: boolean;
}

export interface ResetUserPasswordPayload {
  new_password: string;
}

