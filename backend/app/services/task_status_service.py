from __future__ import annotations

from uuid import uuid4

from fastapi import HTTPException

from ..core.api_errors import raise_api_error
from ..core.config import resolve_consensus_strategy
from ..models.message import BusMessage, MessageType
from ..models.task import Task, TaskStatus, TaskStatusUpdate
from .consensus import ConsensusService
from .message_bus import InMemoryMessageBus
from .store_contract import StoreContract


class TaskStatusService:
    """Encapsulates task status mutations and event publishing."""

    _ALLOWED_STATUS_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.QUEUED: {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.FAILED},
        TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED},
        TaskStatus.COMPLETED: set(),
        TaskStatus.FAILED: set(),
    }

    def __init__(self, *, store: StoreContract, bus: InMemoryMessageBus) -> None:
        self.store = store
        self.bus = bus

    def resolve_working_agent(self, *, task_id: str, requested_agent_id: str | None) -> tuple[Task, str]:
        task = self.store.get_task(task_id)
        if not task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法开始执行。",
                operation="resolve_working_agent",
                detail="Task not found",
                task_id=task_id,
            )

        working_agent = requested_agent_id or task.current_agent_id or (
            task.assigned_agent_ids[0] if task.assigned_agent_ids else None
        )
        if not working_agent:
            raise_api_error(
                409,
                error_code="E_TASK_NO_EXECUTION_AGENT",
                user_message="当前任务没有可执行的 Agent，请先分配或指定 Agent。",
                operation="resolve_working_agent",
                detail="No agent available for execution",
                task_id=task_id,
                task_status=task.status.value,
                retryable=True,
            )
        if not self.store.get_agent(working_agent):
            raise_api_error(
                404,
                error_code="E_AGENT_NOT_FOUND",
                user_message="指定的 Agent 不存在。",
                operation="resolve_working_agent",
                detail="Agent not found",
                task_id=task_id,
                agent_id=working_agent,
            )

        if not task.current_agent_id:
            claimed = self.store.claim_task(task_id, working_agent)
            if claimed:
                task = claimed
                self.publish_event(
                    event_type=MessageType.TASK_CLAIM,
                    task_id=task_id,
                    sender=working_agent,
                    payload={"agent_id": working_agent, "note": "auto-claim for execution"},
                )

        return task, working_agent

    def claim_task(self, *, task_id: str, agent_id: str, note: str | None = None) -> Task:
        task = self.store.get_task(task_id)
        if not task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法 claim。",
                operation="claim_task",
                detail="Task not found",
                task_id=task_id,
                agent_id=agent_id,
            )
        if task.status == TaskStatus.COMPLETED:
            raise_api_error(
                409,
                error_code="E_TASK_TERMINAL_CLAIM",
                user_message="已完成任务不能再被 claim。",
                operation="claim_task",
                detail="Completed task cannot be claimed",
                task_id=task_id,
                agent_id=agent_id,
                task_status=task.status.value,
                retryable=False,
            )
        if not self.store.get_agent(agent_id):
            raise_api_error(
                404,
                error_code="E_AGENT_NOT_FOUND",
                user_message="指定的 Agent 不存在。",
                operation="claim_task",
                detail="Agent not found",
                task_id=task_id,
                agent_id=agent_id,
            )
        if task.current_agent_id and task.current_agent_id != agent_id:
            claimed_manually = bool(task.metadata.get("manual_claimed")) if isinstance(task.metadata, dict) else False
            if claimed_manually or agent_id not in task.assigned_agent_ids:
                raise_api_error(
                    409,
                    error_code="E_TASK_ALREADY_CLAIMED",
                    user_message="该任务已被其他 Agent 占用。",
                    operation="claim_task",
                    detail="Task already claimed by another agent",
                    task_id=task_id,
                    agent_id=agent_id,
                    task_status=task.status.value,
                    extras={"current_agent_id": task.current_agent_id},
                )

        if isinstance(task.metadata, dict):
            task.metadata["manual_claimed"] = True

        claimed_task = self.store.claim_task(task_id, agent_id)
        if not claimed_task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法 claim。",
                operation="claim_task",
                detail="Task not found",
                task_id=task_id,
                agent_id=agent_id,
            )

        self.publish_event(
            event_type=MessageType.TASK_CLAIM,
            task_id=task_id,
            sender=agent_id,
            payload={"agent_id": agent_id, "note": note},
        )
        return claimed_task

    def handoff_task(self, *, task_id: str, from_agent_id: str, to_agent_id: str, reason: str | None = None) -> Task:
        task = self.store.get_task(task_id)
        if not task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法交接。",
                operation="handoff_task",
                detail="Task not found",
                task_id=task_id,
                agent_id=from_agent_id,
            )
        if task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
            raise_api_error(
                409,
                error_code="E_TASK_TERMINAL_HANDOFF",
                user_message="终态任务不能再进行交接。",
                operation="handoff_task",
                detail="Terminal task cannot be handed off",
                task_id=task_id,
                agent_id=from_agent_id,
                task_status=task.status.value,
                retryable=task.status == TaskStatus.FAILED,
            )
        if task.current_agent_id != from_agent_id:
            raise_api_error(
                409,
                error_code="E_TASK_HANDOFF_OWNER_MISMATCH",
                user_message="当前任务并不属于发起交接的 Agent。",
                operation="handoff_task",
                detail="Task is not currently owned by from_agent_id",
                task_id=task_id,
                agent_id=from_agent_id,
                task_status=task.status.value,
                extras={"current_agent_id": task.current_agent_id, "to_agent_id": to_agent_id},
            )
        if not self.store.get_agent(to_agent_id):
            raise_api_error(
                404,
                error_code="E_AGENT_NOT_FOUND",
                user_message="目标 Agent 不存在，无法交接。",
                operation="handoff_task",
                detail="Target agent not found",
                task_id=task_id,
                agent_id=to_agent_id,
                extras={"from_agent_id": from_agent_id},
            )

        updated_task = self.store.handoff_task(task_id, from_agent_id, to_agent_id, reason)
        if not updated_task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法交接。",
                operation="handoff_task",
                detail="Task not found",
                task_id=task_id,
                agent_id=from_agent_id,
                extras={"to_agent_id": to_agent_id},
            )

        self.publish_event(
            event_type=MessageType.TASK_HANDOFF,
            task_id=task_id,
            sender=from_agent_id,
            receiver=to_agent_id,
            payload={
                "from_agent_id": from_agent_id,
                "to_agent_id": to_agent_id,
                "reason": reason,
            },
        )
        return updated_task

    def apply_status_update(self, task_id: str, payload: TaskStatusUpdate, consensus_service: ConsensusService) -> Task:
        existing_task = self.store.get_task(task_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail="Task not found")
        previous_status = existing_task.status
        self._validate_status_transition(previous_status, payload.status)

        task = self.store.update_task_status(task_id, payload)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        self.publish_event(
            event_type=MessageType.TASK_UPDATE,
            task_id=task_id,
            sender="api_gateway",
            payload={"status": task.status.value, "progress": task.progress},
        )
        if task.result is not None:
            self.publish_event(
                event_type=MessageType.TASK_RESULT,
                task_id=task_id,
                sender="api_gateway",
                payload={"result": task.result},
            )
        if payload.agent_id and payload.result is not None:
            self.publish_event(
                event_type=MessageType.VOTE,
                task_id=task_id,
                sender=payload.agent_id,
                payload={
                    "agent_id": payload.agent_id,
                    "confidence": payload.confidence,
                    "result": payload.result,
                },
            )

        strategy, strategy_note = resolve_consensus_strategy(task.metadata)
        consensus = consensus_service.evaluate(task, strategy=strategy)
        if consensus is not None:
            if strategy_note:
                consensus.reason = f"{consensus.reason} {strategy_note}"
            task = self.store.set_task_consensus(task_id, consensus) or task
            if consensus.conflict_detected:
                self.publish_event(
                    event_type=MessageType.CONFLICT_NOTICE,
                    task_id=task_id,
                    sender="consensus_engine",
                    payload={
                        "reason": consensus.reason,
                        "proposal_count": len(task.proposals),
                        "explanation": consensus.explanation,
                    },
                )

            self.publish_event(
                event_type=MessageType.DECISION,
                task_id=task_id,
                sender="consensus_engine",
                payload={
                    "conflict_detected": consensus.conflict_detected,
                    "decision_result": consensus.decision_result,
                    "decided_by": consensus.decided_by,
                    "reason": consensus.reason,
                    "explanation": consensus.explanation,
                },
            )

        if task.status == TaskStatus.COMPLETED and previous_status != TaskStatus.COMPLETED:
            self.publish_event(
                event_type=MessageType.TASK_COMPLETE,
                task_id=task_id,
                sender="workflow_engine",
                payload={
                    "status": task.status.value,
                    "progress": task.progress,
                    "result": task.result,
                    "consensus": task.consensus.model_dump(mode="json") if task.consensus else None,
                },
            )

        if task.status == TaskStatus.FAILED and previous_status != TaskStatus.FAILED:
            error_message = payload.error_message
            error_details: dict[str, object] | None = None
            if isinstance(task.result, dict):
                if not error_message:
                    error_field = task.result.get("error")
                    if isinstance(error_field, str):
                        error_message = error_field
                details_field = task.result.get("error_details")
                if isinstance(details_field, dict):
                    error_details = details_field

            self.publish_event(
                event_type=MessageType.TASK_FAILED,
                task_id=task_id,
                sender="workflow_engine",
                payload={
                    "status": task.status.value,
                    "progress": task.progress,
                    "error_code": payload.error_code,
                    "error_message": error_message,
                    "error_category": error_details.get("error_category") if error_details else None,
                    "retryable": error_details.get("retryable") if error_details else None,
                    "user_message": error_details.get("user_message") if error_details else None,
                    "result": task.result,
                },
            )

        return task

    def _validate_status_transition(self, previous_status: TaskStatus, next_status: TaskStatus) -> None:
        # Idempotent writes are allowed so repeated updates do not break UI polling/replays.
        if previous_status == next_status:
            return

        allowed_targets = self._ALLOWED_STATUS_TRANSITIONS.get(previous_status, set())
        if next_status in allowed_targets:
            return

        detail = {
            "from_status": previous_status.value,
            "to_status": next_status.value,
        }
        if previous_status == TaskStatus.FAILED:
            detail["hint"] = "Use /api/tasks/{task_id}/retry before resuming execution"

        raise_api_error(
            409,
            error_code="E_TASK_INVALID_STATUS_TRANSITION",
            user_message=f"Invalid status transition: {previous_status.value} -> {next_status.value}",
            operation="update_task_status",
            detail="Task status transition is not allowed",
            task_status=previous_status.value,
            retryable=previous_status == TaskStatus.FAILED,
            extras=detail,
        )

    def publish_event(
        self,
        *,
        event_type: MessageType,
        task_id: str,
        sender: str,
        payload: dict[str, object],
        receiver: str | None = None,
    ) -> None:
        self.bus.publish(
            BusMessage(
                message_id=f"msg_{uuid4().hex[:8]}",
                type=event_type,
                sender=sender,
                receiver=receiver,
                task_id=task_id,
                payload=payload,
            )
        )
