from __future__ import annotations

from ..core.api_errors import raise_api_error
from ..core.config import (
    get_agent_execution_fallback,
    normalize_arbitration_mode,
    normalize_pipeline_error_policy,
    resolve_max_retries,
)
from ..models.message import MessageType
from ..models.task import (
    Task,
    TaskExecutionPreviewResponse,
    TaskExecutionRequest,
    TaskRetryRequest,
    TaskSimulationRequest,
    TaskStatus,
    TaskStatusUpdate,
)
from . import task_execution_planning
from .agent_execution import AgentExecutionError, AgentExecutionService
from .consensus import ConsensusService
from .store_contract import StoreContract
from .task_status_service import TaskStatusService
from .workflow import WorkflowService


class TaskExecutionCoordinator:
    """Coordinates task simulate/preview/execute/retry flows."""

    def __init__(
        self,
        *,
        store: StoreContract,
        status_service: TaskStatusService,
        consensus_service: ConsensusService,
        execution_service: AgentExecutionService,
    ) -> None:
        self.store = store
        self.status_service = status_service
        self.consensus_service = consensus_service
        self.execution_service = execution_service

    def preview_execute(self, *, task_id: str, payload: TaskExecutionRequest) -> TaskExecutionPreviewResponse:
        task = self.store.get_task(task_id)
        if not task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法预览执行计划。",
                operation="preview_execute",
                detail="Task not found",
                task_id=task_id,
            )

        requested_default_agent_id = payload.agent_id
        if payload.execution_mode in {"pipeline", "parallel"} and payload.pipeline_agent_ids:
            requested_default_agent_id = requested_default_agent_id or payload.pipeline_agent_ids[0]

        default_agent_id = task_execution_planning.resolve_default_execution_agent(task, requested_default_agent_id, self.store)
        preview_task = task
        if payload.execution_mode in {"pipeline", "parallel"} and payload.pipeline_agent_ids:
            preview_task = task.model_copy(deep=True)
            preview_task.current_agent_id = requested_default_agent_id
        plan = task_execution_planning.build_execution_plan(
            task=preview_task,
            payload=payload,
            default_agent_id=default_agent_id,
            store=self.store,
        )
        fallback_mode = payload.fallback_mode or get_agent_execution_fallback()
        arbitration_mode = normalize_arbitration_mode(
            payload.arbitration_mode or str(task.metadata.get("arbitration_mode", "off")),
            default="off",
        )
        pipeline_error_policy = normalize_pipeline_error_policy(payload.pipeline_error_policy, default="fail_fast")
        judge_agent_id = payload.judge_agent_id or str(task.metadata.get("judge_agent_id", "agent_judge"))

        return TaskExecutionPreviewResponse(
            task_id=task_id,
            execution_mode=payload.execution_mode,
            provider=payload.provider,
            pipeline_error_policy=pipeline_error_policy,
            allow_fallback=payload.allow_fallback,
            fallback_mode=fallback_mode,
            arbitration_mode=arbitration_mode,
            judge_agent_id=judge_agent_id,
            steps=plan,
            estimated_events=task_execution_planning.build_preview_estimated_events(payload=payload, steps=plan),
            preview_warnings=task_execution_planning.build_preview_warnings(
                store=self.store,
                payload=payload,
                arbitration_mode=arbitration_mode,
                judge_agent_id=judge_agent_id,
                steps=plan,
                fallback_mode=fallback_mode,
            ),
        )

    def simulate_task_execution(self, *, task_id: str, payload: TaskSimulationRequest) -> Task:
        task = self.store.get_task(task_id)
        if not task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法进行模拟执行。",
                operation="simulate_task_execution",
                detail="Task not found",
                task_id=task_id,
            )

        progress_points = sorted({point for point in payload.progress_points if 0 < point < 100}) or [30, 70]

        if payload.agent_id or task.current_agent_id or task.assigned_agent_ids:
            task, _ = self.status_service.resolve_working_agent(task_id=task_id, requested_agent_id=payload.agent_id)

        if payload.simulate_handoff and task.current_agent_id:
            handoff_target = payload.handoff_to_agent_id
            if not handoff_target:
                candidates = [agent_id for agent_id in task.assigned_agent_ids if agent_id != task.current_agent_id]
                handoff_target = candidates[0] if candidates else None
            if handoff_target:
                if not self.store.get_agent(handoff_target):
                    raise_api_error(
                        404,
                        error_code="E_AGENT_NOT_FOUND",
                        user_message="模拟交接的目标 Agent 不存在。",
                        operation="simulate_task_execution",
                        detail="Target agent not found",
                        task_id=task_id,
                        agent_id=handoff_target,
                    )
                previous_owner = task.current_agent_id
                handed_off = self.store.handoff_task(task_id, previous_owner, handoff_target, "simulator handoff")
                if handed_off:
                    task = handed_off
                    self.status_service.publish_event(
                        event_type=MessageType.TASK_HANDOFF,
                        task_id=task_id,
                        sender=previous_owner,
                        receiver=handoff_target,
                        payload={
                            "from_agent_id": previous_owner,
                            "to_agent_id": handoff_target,
                            "reason": "simulator handoff",
                        },
                    )

        for point in progress_points:
            task = self.status_service.apply_status_update(
                task_id,
                TaskStatusUpdate(
                    status=TaskStatus.IN_PROGRESS,
                    progress=point,
                    agent_id=task.current_agent_id,
                ),
                self.consensus_service,
            )

        effective_mode = payload.mode
        if payload.retry_success_threshold is not None:
            effective_mode = "success" if task.retry_count >= payload.retry_success_threshold else "failure"

        if effective_mode == "success":
            return self.status_service.apply_status_update(
                task_id,
                TaskStatusUpdate(
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    agent_id=task.current_agent_id,
                    result={"summary": "simulated execution completed", "steps": len(progress_points) + 1},
                ),
                self.consensus_service,
            )

        return self.status_service.apply_status_update(
            task_id,
            TaskStatusUpdate(
                status=TaskStatus.FAILED,
                progress=100,
                agent_id=task.current_agent_id,
                error_code=payload.error_code,
                error_message=payload.error_message,
                result={"error": payload.error_message},
            ),
            self.consensus_service,
        )

    def execute_task(self, *, task_id: str, payload: TaskExecutionRequest) -> Task:
        task, working_agent = self.status_service.resolve_working_agent(task_id=task_id, requested_agent_id=payload.agent_id)

        progress_points = sorted({point for point in payload.progress_points if 0 < point < 100}) or [25, 60, 85]
        for point in progress_points:
            task = self.status_service.apply_status_update(
                task_id,
                TaskStatusUpdate(status=TaskStatus.IN_PROGRESS, progress=point, agent_id=working_agent),
                self.consensus_service,
            )

        execution_agents = task_execution_planning.resolve_execution_agents(task, payload, working_agent)
        for agent_id in execution_agents:
            if not self.store.get_agent(agent_id):
                raise_api_error(
                    404,
                    error_code="E_AGENT_NOT_FOUND",
                    user_message="执行链路中包含不存在的 Agent。",
                    operation="execute_task",
                    detail=f"Agent not found: {agent_id}",
                    task_id=task_id,
                    agent_id=agent_id,
                )

        if payload.execution_mode == "pipeline" and len(execution_agents) > 1:
            self.status_service.publish_event(
                event_type=MessageType.TASK_PIPELINE_START,
                task_id=task_id,
                sender="workflow_engine",
                payload={
                    "execution_mode": payload.execution_mode,
                    "steps": len(execution_agents),
                    "agent_ids": execution_agents,
                },
            )

        arbitration_mode = normalize_arbitration_mode(
            payload.arbitration_mode or str(task.metadata.get("arbitration_mode", "off")),
            default="off",
        )
        pipeline_error_policy = normalize_pipeline_error_policy(payload.pipeline_error_policy, default="fail_fast")

        step_outputs: list[dict[str, object]] = []
        error_steps: list[dict[str, object]] = []
        active_owner = task.current_agent_id
        try:
            for index, agent_id in enumerate(execution_agents):
                if payload.execution_mode == "parallel":
                    active_owner = active_owner or agent_id
                elif active_owner and active_owner != agent_id:
                    handed_off = self.store.handoff_task(task_id, active_owner, agent_id, "pipeline step handoff")
                    if handed_off:
                        task = handed_off
                    self.status_service.publish_event(
                        event_type=MessageType.TASK_HANDOFF,
                        task_id=task_id,
                        sender=active_owner,
                        receiver=agent_id,
                        payload={
                            "from_agent_id": active_owner,
                            "to_agent_id": agent_id,
                            "reason": "pipeline step handoff",
                            "step": index + 1,
                        },
                    )
                elif not active_owner:
                    claimed = self.store.claim_task(task_id, agent_id)
                    if claimed:
                        task = claimed
                    self.status_service.publish_event(
                        event_type=MessageType.TASK_CLAIM,
                        task_id=task_id,
                        sender=agent_id,
                        payload={"agent_id": agent_id, "note": "auto-claim for pipeline execution"},
                    )

                active_owner = agent_id
                agent = self.store.get_agent(agent_id)
                if not agent:
                    raise_api_error(
                        404,
                        error_code="E_AGENT_NOT_FOUND",
                        user_message="执行时未找到目标 Agent。",
                        operation="execute_task",
                        detail=f"Agent not found: {agent_id}",
                        task_id=task_id,
                        agent_id=agent_id,
                    )

                self.status_service.publish_event(
                    event_type=MessageType.AGENT_EXECUTION_START,
                    task_id=task_id,
                    sender=agent_id,
                    payload={
                        "step": index + 1,
                        "total_steps": len(execution_agents),
                        "agent_id": agent_id,
                        "agent_role": agent.role,
                        "provider": payload.provider,
                        "model": payload.model,
                    },
                )

                try:
                    execution = self.execution_service.execute(
                        task=task,
                        agent=agent,
                        provider=payload.provider,
                        api_key=payload.api_key,
                        model=payload.model,
                        system_instruction=payload.system_instruction,
                        temperature=payload.temperature,
                        max_tokens=payload.max_tokens,
                    )
                except AgentExecutionError as step_exc:
                    error_payload = step_exc.to_payload(
                        step=index + 1,
                        total_steps=len(execution_agents),
                        agent_id=agent_id,
                        execution_mode=payload.execution_mode,
                        provider=payload.provider,
                        model=payload.model,
                    )
                    self.status_service.publish_event(
                        event_type=MessageType.AGENT_EXECUTION_ERROR,
                        task_id=task_id,
                        sender=agent_id,
                        payload=error_payload,
                    )
                    error_steps.append(error_payload)
                    if payload.execution_mode in {"pipeline", "parallel"} and pipeline_error_policy == "continue":
                        continue
                    raise

                step_result = dict(execution.result)
                step_outputs.append(
                    {
                        "step": index + 1,
                        "agent_id": agent_id,
                        "agent_role": agent.role,
                        "result": step_result,
                        "confidence": execution.confidence,
                        "metrics": getattr(execution, "metrics", None) or {},
                    }
                )
                self.status_service.publish_event(
                    event_type=MessageType.AGENT_EXECUTION_RESULT,
                    task_id=task_id,
                    sender=agent_id,
                    payload={
                        "step": index + 1,
                        "total_steps": len(execution_agents),
                        "agent_id": agent_id,
                        "summary": str(step_result.get("summary", "")),
                        "metrics": getattr(execution, "metrics", None) or {},
                    },
                )

            if not step_outputs:
                if error_steps:
                    last_error = error_steps[-1]
                    raise AgentExecutionError(
                        code=str(last_error.get("error_code", "E_EXECUTION_PROVIDER")),
                        message=str(
                            last_error.get(
                                "error_message",
                                f"{payload.execution_mode} execution produced no successful step",
                            )
                        ),
                        details={
                            "execution_mode": payload.execution_mode,
                            "error_steps": error_steps,
                            "provider": payload.provider,
                            "model": payload.model,
                        },
                    )
                raise AgentExecutionError(
                    code="E_EXECUTION_EMPTY",
                    message=f"{payload.execution_mode} execution produced no successful step",
                    details={
                        "execution_mode": payload.execution_mode,
                        "provider": payload.provider,
                        "model": payload.model,
                    },
                )

            if payload.execution_mode == "pipeline" and len(execution_agents) > 1:
                self.status_service.publish_event(
                    event_type=MessageType.TASK_PIPELINE_FINISH,
                    task_id=task_id,
                    sender="workflow_engine",
                    payload={
                        "execution_mode": payload.execution_mode,
                        "steps": len(execution_agents),
                        "status": "completed",
                    },
                )

            final_step = (
                task_execution_planning.select_primary_step(step_outputs)
                if payload.execution_mode == "parallel"
                else step_outputs[-1]
            )
            result_payload = dict(final_step["result"])
            if payload.execution_mode == "parallel":
                result_payload["parallel"] = {
                    "mode": "batch",
                    "selection": "highest_confidence",
                    "steps": [
                        {
                            "step": int(step.get("step", 0)),
                            "agent_id": str(step.get("agent_id", "")),
                            "agent_role": str(step.get("agent_role", "")),
                            "summary": str((step.get("result") or {}).get("summary", "")),
                            "confidence": float(step.get("confidence", 0.0)),
                            "metrics": step.get("metrics") or {},
                        }
                        for step in step_outputs
                    ],
                }
            elif len(step_outputs) > 1:
                result_payload["pipeline"] = {
                    "mode": "serial",
                    "steps": [
                        {
                            "agent_id": str(step.get("agent_id", "")),
                            "agent_role": str(step.get("agent_role", "")),
                            "summary": str((step.get("result") or {}).get("summary", "")),
                            "metrics": step.get("metrics") or {},
                        }
                        for step in step_outputs
                    ],
                }
            if error_steps:
                if payload.execution_mode == "parallel":
                    result_payload.setdefault("parallel", {"mode": "batch", "steps": []})
                    result_payload["parallel"]["errors"] = error_steps
                else:
                    result_payload.setdefault("pipeline", {"mode": "serial", "steps": []})
                    result_payload["pipeline"]["errors"] = error_steps

            self._apply_arbitration(
                task=task,
                payload=payload,
                result_payload=result_payload,
                step_outputs=step_outputs,
                arbitration_mode=arbitration_mode,
            )

            result_payload.setdefault("execution_metrics", final_step.get("metrics") or {})
            if not isinstance(result_payload["execution_metrics"], dict):
                result_payload["execution_metrics"] = {}
            result_payload["execution_metrics"].update(
                {
                    "arbitration_mode": arbitration_mode,
                    "judge_triggered": bool(result_payload.get("arbitration", {}).get("decision") in {"judge_override", "primary_kept"}),
                    "execution_mode": payload.execution_mode,
                    "pipeline_error_policy": pipeline_error_policy,
                    "pipeline_error_count": len(error_steps),
                    "parallel_steps": len(execution_agents) if payload.execution_mode == "parallel" else None,
                    "selected_agent_id": str(final_step.get("agent_id", working_agent)),
                }
            )
            if payload.execution_mode != "parallel":
                result_payload["execution_metrics"]["pipeline_steps"] = len(execution_agents)

            if payload.execution_mode == "parallel":
                selected_agent_id = str(final_step.get("agent_id", working_agent))
                if task.current_agent_id != selected_agent_id:
                    selected_claim = self.store.claim_task(task_id, selected_agent_id)
                    if selected_claim:
                        task = selected_claim
                    self.status_service.publish_event(
                        event_type=MessageType.TASK_CLAIM,
                        task_id=task_id,
                        sender=selected_agent_id,
                        payload={"agent_id": selected_agent_id, "note": "selected as parallel winner"},
                    )
            return self.status_service.apply_status_update(
                task_id,
                TaskStatusUpdate(
                    status=TaskStatus.COMPLETED,
                    progress=100,
                    agent_id=str(final_step.get("agent_id", working_agent)),
                    confidence=float(final_step.get("confidence", 0.75)),
                    result=result_payload,
                ),
                self.consensus_service,
            )
        except AgentExecutionError as exc:
            if active_owner and not error_steps:
                self.status_service.publish_event(
                    event_type=MessageType.AGENT_EXECUTION_ERROR,
                    task_id=task_id,
                    sender=active_owner,
                    payload=exc.to_payload(
                        agent_id=active_owner,
                        execution_mode=payload.execution_mode,
                        provider=payload.provider,
                        model=payload.model,
                    ),
                )

            fallback_mode = payload.fallback_mode or get_agent_execution_fallback()
            normalized_error = exc.to_payload(
                agent_id=working_agent,
                execution_mode=payload.execution_mode,
                provider=payload.provider,
                model=payload.model,
                fallback_mode=fallback_mode,
                allow_fallback=payload.allow_fallback,
            )
            if payload.allow_fallback and fallback_mode == "simulate":
                if payload.execution_mode == "pipeline" and len(execution_agents) > 1:
                    self.status_service.publish_event(
                        event_type=MessageType.TASK_PIPELINE_FINISH,
                        task_id=task_id,
                        sender="workflow_engine",
                        payload={
                            "execution_mode": payload.execution_mode,
                            "steps": len(execution_agents),
                            "status": "fallback_completed",
                        },
                    )
                return self.status_service.apply_status_update(
                    task_id,
                    TaskStatusUpdate(
                        status=TaskStatus.COMPLETED,
                        progress=100,
                        agent_id=working_agent,
                        confidence=0.55,
                        result={
                            "summary": f"fallback simulated completion: {task.objective}",
                            "mode": "fallback_simulated",
                            "fallback_reason": exc.message,
                            "fallback_code": exc.code,
                            "fallback_error": normalized_error,
                            "agent_id": working_agent,
                            "execution_metrics": {
                                "fallback": True,
                                "fallback_mode": fallback_mode,
                                "arbitration_mode": arbitration_mode,
                                "execution_mode": payload.execution_mode,
                                "pipeline_steps": len(execution_agents)
                                if payload.execution_mode != "parallel"
                                else None,
                                "pipeline_error_policy": pipeline_error_policy,
                                "pipeline_error_count": len(error_steps) if error_steps else 1,
                                "parallel_steps": len(execution_agents)
                                if payload.execution_mode == "parallel"
                                else None,
                                "selected_agent_id": working_agent,
                            },
                        },
                    ),
                    self.consensus_service,
                )

            if payload.execution_mode == "pipeline" and len(execution_agents) > 1:
                self.status_service.publish_event(
                    event_type=MessageType.TASK_PIPELINE_FINISH,
                    task_id=task_id,
                    sender="workflow_engine",
                    payload={
                        "execution_mode": payload.execution_mode,
                        "steps": len(execution_agents),
                        "status": "failed",
                    },
                )

            return self.status_service.apply_status_update(
                task_id,
                TaskStatusUpdate(
                    status=TaskStatus.FAILED,
                    progress=100,
                    agent_id=working_agent,
                    error_code=exc.code,
                    error_message=exc.message,
                    result={"error": exc.message, "error_details": normalized_error},
                ),
                self.consensus_service,
            )

    def retry_task(self, *, task_id: str, payload: TaskRetryRequest, workflow: WorkflowService) -> Task:
        task = self.store.get_task(task_id)
        if not task:
            raise_api_error(
                404,
                error_code="E_TASK_NOT_FOUND",
                user_message="任务不存在，无法重试。",
                operation="retry_task",
                detail="Task not found",
                task_id=task_id,
            )
        if task.status != TaskStatus.FAILED:
            raise_api_error(
                409,
                error_code="E_TASK_RETRY_INVALID_STATE",
                user_message="只有失败任务才能重试。",
                operation="retry_task",
                detail="Only failed tasks can be retried",
                task_id=task_id,
                task_status=task.status.value,
                retryable=False,
            )

        max_retries = resolve_max_retries(task.metadata)
        if task.retry_count >= max_retries:
            self.status_service.publish_event(
                event_type=MessageType.TASK_RETRY_EXHAUSTED,
                task_id=task_id,
                sender="workflow_engine",
                payload={
                    "retry_count": task.retry_count,
                    "max_retries": max_retries,
                    "reason": "retry limit reached",
                },
            )
            raise_api_error(
                409,
                error_code="E_TASK_RETRY_EXHAUSTED",
                user_message="已达到重试上限。请先提高 max_retries 或排查失败原因后再重试。",
                operation="retry_task",
                detail="Retry limit reached",
                task_id=task_id,
                task_status=task.status.value,
                retryable=False,
                extras={"retry_count": task.retry_count, "max_retries": max_retries},
            )

        retried = self.store.retry_task(task_id, reason=payload.reason)
        if not retried:
            raise_api_error(
                409,
                error_code="E_TASK_RETRY_INVALID_STATE",
                user_message="只有失败任务才能重试。",
                operation="retry_task",
                detail="Only failed tasks can be retried",
                task_id=task_id,
                task_status=task.status.value,
                retryable=False,
            )

        self.status_service.publish_event(
            event_type=MessageType.TASK_RETRY,
            task_id=task_id,
            sender="workflow_engine",
            payload={
                "retry_count": retried.retry_count,
                "max_retries": max_retries,
                "reason": payload.reason,
                "status": retried.status.value,
            },
        )

        if payload.requeue:
            workflow.requeue_task(task_id, reason=payload.reason, force=True)
            return self.store.get_task(task_id) or retried
        return retried

    def _apply_arbitration(
        self,
        *,
        task: Task,
        payload: TaskExecutionRequest,
        result_payload: dict[str, object],
        step_outputs: list[dict[str, object]],
        arbitration_mode: str,
    ) -> None:
        current_summary = str(result_payload.get("summary", ""))
        judge_triggered = False
        judge_notes: dict[str, object] | None = None

        should_run_judge = arbitration_mode == "judge_always" or (
            arbitration_mode == "judge_on_conflict"
            and (
                task_execution_planning.has_conflicting_step_outputs(step_outputs)
                if payload.execution_mode == "parallel"
                else self._has_conflicting_proposals(task, current_summary)
            )
        )

        if should_run_judge:
            judge_agent_id = payload.judge_agent_id or str(task.metadata.get("judge_agent_id", "agent_judge"))
            judge_agent = self.store.get_agent(judge_agent_id)
            if judge_agent:
                judge_execution = self.execution_service.execute(
                    task=task,
                    agent=judge_agent,
                    provider=payload.provider,
                    api_key=payload.api_key,
                    model=payload.model,
                    system_instruction=(
                        "You are the judge agent for arbitration. Review conflicting outcomes and provide the final decision summary."
                    ),
                    temperature=0.1,
                    max_tokens=payload.max_tokens,
                )
                judge_triggered = True
                judge_summary = str(judge_execution.result.get("summary", "")).strip()
                primary_summary = str(result_payload.get("summary", "")).strip()
                decision = "primary_kept"
                if judge_summary and judge_summary.lower() != primary_summary.lower():
                    result_payload["summary"] = judge_summary
                    decision = "judge_override"

                judge_notes = {
                    "mode": arbitration_mode,
                    "judge_agent_id": judge_agent_id,
                    "decision": decision,
                    "judge_summary": judge_summary,
                    "judge_metrics": getattr(judge_execution, "metrics", None) or {},
                    "judge_triggered": judge_triggered,
                    "explanation": {
                        "conflict_detected": True,
                        "primary_summary": primary_summary,
                        "judge_summary": judge_summary,
                        "selected_summary": str(result_payload.get("summary", "")).strip(),
                        "selection_basis": (
                            "judge override applied"
                            if decision == "judge_override"
                            else "judge reviewed and kept primary summary"
                        ),
                    },
                }
            else:
                judge_notes = {
                    "mode": arbitration_mode,
                    "judge_agent_id": judge_agent_id,
                    "decision": "judge_unavailable",
                    "reason": "judge agent not found; kept primary summary",
                    "judge_triggered": judge_triggered,
                    "explanation": {
                        "conflict_detected": True,
                        "selected_summary": str(result_payload.get("summary", "")).strip(),
                        "selection_basis": "judge unavailable; kept primary summary",
                    },
                }

        if judge_notes:
            result_payload["arbitration"] = judge_notes

    @staticmethod
    def _has_conflicting_proposals(task: Task, current_summary: str) -> bool:
        normalized = current_summary.strip().lower()
        for proposal in task.proposals:
            existing_summary = str(proposal.result.get("summary", "")).strip().lower()
            if existing_summary and existing_summary != normalized:
                return True
        return False

