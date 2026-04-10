from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskCreate(BaseModel):
    objective: str = Field(min_length=3, max_length=1000)
    priority: TaskPriority = TaskPriority.MEDIUM
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskProposal(BaseModel):
    agent_id: str
    result: dict[str, Any]
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskConsensus(BaseModel):
    conflict_detected: bool
    decision_result: dict[str, Any]
    decided_by: str = "rule_based"
    reason: str
    explanation: dict[str, Any] | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskHandoffRecord(BaseModel):
    from_agent_id: str
    to_agent_id: str
    reason: str | None = None
    handed_off_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskAttemptRecord(BaseModel):
    attempt_number: int = Field(ge=1)
    outcome: Literal["failed", "retried", "completed"]
    reason: str | None = None
    error_code: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Task(BaseModel):
    task_id: str
    owner_user_id: str | None = None
    owner_username: str | None = None
    objective: str
    priority: TaskPriority
    status: TaskStatus = TaskStatus.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    assigned_agent_ids: list[str] = Field(default_factory=list)
    current_agent_id: str | None = None
    handoff_history: list[TaskHandoffRecord] = Field(default_factory=list)
    attempt_history: list[TaskAttemptRecord] = Field(default_factory=list)
    retry_count: int = 0
    last_retry_at: datetime | None = None
    proposals: list[TaskProposal] = Field(default_factory=list)
    consensus: TaskConsensus | None = None
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskStatusUpdate(BaseModel):
    status: TaskStatus
    progress: int = Field(default=0, ge=0, le=100)
    agent_id: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    error_code: str | None = None
    error_message: str | None = None
    result: dict[str, Any] | None = None


class TaskClaimRequest(BaseModel):
    agent_id: str = Field(min_length=3, max_length=120)
    note: str | None = Field(default=None, max_length=400)


class TaskHandoffRequest(BaseModel):
    from_agent_id: str = Field(min_length=3, max_length=120)
    to_agent_id: str = Field(min_length=3, max_length=120)
    reason: str | None = Field(default=None, max_length=400)


class TaskSimulationRequest(BaseModel):
    mode: Literal["success", "failure"] = "success"
    agent_id: str | None = Field(default=None, min_length=3, max_length=120)
    progress_points: list[int] = Field(default_factory=lambda: [30, 70])
    simulate_handoff: bool = False
    handoff_to_agent_id: str | None = Field(default=None, min_length=3, max_length=120)
    retry_success_threshold: int | None = Field(default=None, ge=1, le=10)
    error_code: str = "E_SIMULATED"
    error_message: str = "simulated execution failed"


class TaskExecutionRequest(BaseModel):
    agent_id: str | None = Field(default=None, min_length=3, max_length=120)
    execution_mode: Literal["single", "pipeline", "parallel"] = "single"
    pipeline_agent_ids: list[str] = Field(default_factory=list)
    pipeline_error_policy: Literal["fail_fast", "continue"] = "fail_fast"
    progress_points: list[int] = Field(default_factory=lambda: [25, 60, 85])
    provider: Literal["openai_compatible"] = "openai_compatible"
    api_key: str | None = Field(default=None, min_length=8, max_length=512)
    model: str | None = Field(default=None, max_length=200)
    system_instruction: str | None = Field(default=None, max_length=2000)
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)
    max_tokens: int = Field(default=800, ge=100, le=4000)
    allow_fallback: bool = True
    fallback_mode: Literal["simulate", "fail"] | None = None
    arbitration_mode: Literal["off", "judge_on_conflict", "judge_always"] = "off"
    judge_agent_id: str | None = Field(default=None, min_length=3, max_length=120)


class TaskRetryRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=400)
    requeue: bool = True


class TaskExecutionPlanStep(BaseModel):
    step: int
    agent_id: str
    agent_role: str
    transition_action: Literal["claim", "handoff", "keep", "parallel_dispatch"]
    transition_from_agent_id: str | None = None


class TaskExecutionPreviewEvent(BaseModel):
    event_type: Literal[
        "TaskPipelineStart",
        "AgentExecutionStart",
        "AgentExecutionResult",
        "AgentExecutionError",
        "TaskPipelineFinish",
        "TaskResult",
        "TaskComplete",
        "TaskFailed",
    ]
    condition: Literal["always", "on_error", "on_fallback", "on_no_fallback"] = "always"
    step: int | None = None
    agent_id: str | None = None
    note: str | None = None


class TaskExecutionPreviewWarning(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning"] = "warning"
    applies_to_step: int | None = None


class TaskExecutionPreviewResponse(BaseModel):
    task_id: str
    execution_mode: Literal["single", "pipeline", "parallel"]
    provider: Literal["openai_compatible"]
    pipeline_error_policy: Literal["fail_fast", "continue"]
    allow_fallback: bool
    fallback_mode: Literal["simulate", "fail"]
    arbitration_mode: Literal["off", "judge_on_conflict", "judge_always"]
    judge_agent_id: str | None = None
    steps: list[TaskExecutionPlanStep] = Field(default_factory=list)
    estimated_events: list[TaskExecutionPreviewEvent] = Field(default_factory=list)
    preview_warnings: list[TaskExecutionPreviewWarning] = Field(default_factory=list)


class TaskResultResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: dict[str, Any] | None = None
    consensus: TaskConsensus | None = None
    updated_at: datetime


class TaskConsensusResponse(BaseModel):
    task_id: str
    consensus: TaskConsensus | None = None
    proposals: list[TaskProposal] = Field(default_factory=list)


class TaskAttemptsResponse(BaseModel):
    task_id: str
    retry_count: int
    max_retries: int
    items: list[TaskAttemptRecord] = Field(default_factory=list)


