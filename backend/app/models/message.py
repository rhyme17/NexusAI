from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    TASK_REQUEST = "TaskRequest"
    TASK_CLAIM = "TaskClaim"
    TASK_UPDATE = "TaskUpdate"
    TASK_RESULT = "TaskResult"
    TASK_HANDOFF = "TaskHandoff"
    TASK_REJECT = "TaskReject"
    TASK_RETRY = "TaskRetry"
    TASK_RETRY_EXHAUSTED = "TaskRetryExhausted"
    VOTE = "Vote"
    CONFLICT_NOTICE = "ConflictNotice"
    DECISION = "Decision"
    TASK_COMPLETE = "TaskComplete"
    TASK_FAILED = "TaskFailed"
    TASK_PIPELINE_START = "TaskPipelineStart"
    TASK_PIPELINE_FINISH = "TaskPipelineFinish"
    AGENT_EXECUTION_START = "AgentExecutionStart"
    AGENT_EXECUTION_RESULT = "AgentExecutionResult"
    AGENT_EXECUTION_ERROR = "AgentExecutionError"


class BusMessage(BaseModel):
    """Minimal message contract kept for future Message Bus integration."""

    message_id: str
    type: MessageType
    sender: str
    receiver: str | None = None
    task_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskEventsResponse(BaseModel):
    total_count: int
    offset: int
    limit: int
    sort: Literal["asc", "desc"]
    has_more: bool
    next_cursor: str | None = None
    items: list[BusMessage] = Field(default_factory=list)


