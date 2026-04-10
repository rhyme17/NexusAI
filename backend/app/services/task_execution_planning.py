from __future__ import annotations

from typing import Literal

from fastapi import HTTPException

from ..core.config import normalize_arbitration_mode, normalize_pipeline_error_policy
from ..models.task import (
    Task,
    TaskExecutionPlanStep,
    TaskExecutionPreviewEvent,
    TaskExecutionPreviewWarning,
    TaskExecutionRequest,
)
from .agent_execution import AgentExecutionError
from .store_contract import StoreContract


def resolve_execution_agents(task: Task, payload: TaskExecutionRequest, default_agent_id: str) -> list[str]:
    if payload.execution_mode in {"pipeline", "parallel"}:
        ordered = [agent_id for agent_id in payload.pipeline_agent_ids if agent_id]
        if ordered:
            return ordered
        if task.assigned_agent_ids:
            return list(task.assigned_agent_ids)
    return [payload.agent_id or default_agent_id]


def resolve_default_execution_agent(task: Task, requested_agent_id: str | None, store: StoreContract) -> str:
    if requested_agent_id:
        return requested_agent_id

    candidates: list[str] = []
    if task.current_agent_id:
        candidates.append(task.current_agent_id)
    candidates.extend([agent_id for agent_id in task.assigned_agent_ids if agent_id not in candidates])

    if not candidates:
        raise HTTPException(status_code=409, detail="No agent available for execution")

    preferred_roles = _preferred_roles_for_objective(task.objective)
    for preferred_role in preferred_roles:
        for agent_id in candidates:
            agent = store.get_agent(agent_id)
            if agent and agent.role.strip().lower() == preferred_role:
                return agent_id

    working_agent = candidates[0]
    if not working_agent:
        raise HTTPException(status_code=409, detail="No agent available for execution")
    return working_agent


def _preferred_roles_for_objective(objective: str) -> list[str]:
    normalized = objective.strip().lower()
    report_keywords = ["report", "research", "analysis", "summary", "调研", "研究", "报告", "分析"]
    planning_keywords = ["plan", "roadmap", "milestone", "timeline", "计划", "方案", "路线图"]
    if any(keyword in normalized for keyword in report_keywords):
        return ["writer", "analyst", "research", "reviewer", "planner"]
    if any(keyword in normalized for keyword in planning_keywords):
        return ["planner", "analyst", "writer", "research"]
    return ["analyst", "writer", "research", "planner", "reviewer", "judge"]


def build_execution_plan(
    *,
    task: Task,
    payload: TaskExecutionRequest,
    default_agent_id: str,
    store: InMemoryStore,
) -> list[TaskExecutionPlanStep]:
    execution_agents = resolve_execution_agents(task, payload, default_agent_id)
    plan: list[TaskExecutionPlanStep] = []
    previous_owner = task.current_agent_id

    for index, agent_id in enumerate(execution_agents):
        agent = store.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

        if payload.execution_mode == "parallel":
            transition_action: Literal["claim", "handoff", "keep", "parallel_dispatch"] = "parallel_dispatch"
            transition_from = previous_owner
        elif index == 0 and previous_owner is None:
            transition_action = "claim"
            transition_from = None
        elif previous_owner and previous_owner != agent_id:
            transition_action = "handoff"
            transition_from = previous_owner
        else:
            transition_action = "keep"
            transition_from = previous_owner

        plan.append(
            TaskExecutionPlanStep(
                step=index + 1,
                agent_id=agent_id,
                agent_role=agent.role,
                transition_action=transition_action,
                transition_from_agent_id=transition_from,
            )
        )
        previous_owner = agent_id

    return plan


def has_conflicting_step_outputs(step_outputs: list[dict[str, object]]) -> bool:
    summaries = {
        str((step.get("result") or {}).get("summary", "")).strip().lower()
        for step in step_outputs
        if str((step.get("result") or {}).get("summary", "")).strip()
    }
    return len(summaries) > 1


def select_primary_step(step_outputs: list[dict[str, object]]) -> dict[str, object]:
    if not step_outputs:
        raise AgentExecutionError(code="E_EXECUTION_EMPTY", message="parallel execution produced no successful step")
    return max(
        step_outputs,
        key=lambda step: (
            float(step.get("confidence", 0.0)),
            -int(step.get("step", 0)),
        ),
    )


def build_preview_estimated_events(
    *,
    payload: TaskExecutionRequest,
    steps: list[TaskExecutionPlanStep],
) -> list[TaskExecutionPreviewEvent]:
    events: list[TaskExecutionPreviewEvent] = []

    if payload.execution_mode == "pipeline" and len(steps) > 1:
        events.append(
            TaskExecutionPreviewEvent(
                event_type="TaskPipelineStart",
                condition="always",
                note="Published before serial pipeline agent execution begins.",
            )
        )

    for step in steps:
        events.append(
            TaskExecutionPreviewEvent(
                event_type="AgentExecutionStart",
                condition="always",
                step=step.step,
                agent_id=step.agent_id,
                note=(
                    f"Step {step.step}: {step.agent_id}"
                    if payload.execution_mode != "parallel"
                    else f"Parallel dispatch {step.step}: {step.agent_id}"
                ),
            )
        )
        events.append(
            TaskExecutionPreviewEvent(
                event_type="AgentExecutionResult",
                condition="always",
                step=step.step,
                agent_id=step.agent_id,
                note=(
                    f"Step {step.step}: emitted when provider call succeeds."
                    if payload.execution_mode != "parallel"
                    else f"Parallel agent {step.agent_id}: emitted when provider call succeeds."
                ),
            )
        )

    events.append(
        TaskExecutionPreviewEvent(
            event_type="AgentExecutionError",
            condition="on_error",
            note="Published for provider/config/runtime execution failures.",
        )
    )

    if payload.execution_mode == "pipeline" and len(steps) > 1:
        events.append(
            TaskExecutionPreviewEvent(
                event_type="TaskPipelineFinish",
                condition="always",
                note="Published when pipeline completes successfully.",
            )
        )
        events.append(
            TaskExecutionPreviewEvent(
                event_type="TaskPipelineFinish",
                condition="on_error",
                note="Also published when pipeline exits via fallback or failure.",
            )
        )

    events.append(
        TaskExecutionPreviewEvent(
            event_type="TaskResult",
            condition="always",
            note=(
                "Result snapshot event after completion or fallback completion."
                if payload.execution_mode != "parallel"
                else "Result snapshot event after parallel aggregation using the highest-confidence successful agent output."
            ),
        )
    )
    events.append(
        TaskExecutionPreviewEvent(
            event_type="TaskComplete",
            condition="always",
            note="Terminal success event when task finishes with a result.",
        )
    )
    events.append(
        TaskExecutionPreviewEvent(
            event_type="TaskFailed",
            condition="on_no_fallback",
            note="Terminal failure event when fallback is disabled or fallback mode is fail.",
        )
    )

    if payload.allow_fallback:
        events.append(
            TaskExecutionPreviewEvent(
                event_type="TaskComplete",
                condition="on_fallback",
                note="Completion can still occur via fallback simulation.",
            )
        )

    return events


def build_preview_warnings(
    *,
    store: InMemoryStore,
    payload: TaskExecutionRequest,
    arbitration_mode: str,
    judge_agent_id: str,
    steps: list[TaskExecutionPlanStep],
    fallback_mode: str,
) -> list[TaskExecutionPreviewWarning]:
    warnings: list[TaskExecutionPreviewWarning] = []

    if arbitration_mode in {"judge_always", "judge_on_conflict"} and not store.get_agent(judge_agent_id):
        warnings.append(
            TaskExecutionPreviewWarning(
                code="W_PREVIEW_JUDGE_MISSING",
                message=(
                    f"Judge agent '{judge_agent_id}' is not registered. "
                    "Judge arbitration may be skipped or degraded."
                ),
                severity="warning",
            )
        )

    if not payload.allow_fallback or fallback_mode != "simulate":
        warnings.append(
            TaskExecutionPreviewWarning(
                code="W_PREVIEW_STRICT_FAILURE_PATH",
                message="Execution errors will end in TaskFailed because fallback simulation is not enabled.",
                severity="info",
            )
        )

    if payload.execution_mode == "pipeline" and normalize_pipeline_error_policy(payload.pipeline_error_policy) == "continue":
        warnings.append(
            TaskExecutionPreviewWarning(
                code="W_PREVIEW_PARTIAL_PIPELINE",
                message="Pipeline is configured to continue after step errors; final result may include partial step outputs.",
                severity="info",
            )
        )

    if payload.execution_mode == "parallel" and normalize_pipeline_error_policy(payload.pipeline_error_policy) == "continue":
        warnings.append(
            TaskExecutionPreviewWarning(
                code="W_PREVIEW_PARTIAL_PARALLEL",
                message="Parallel execution is configured to continue after agent errors; the final result may be aggregated from partial successes.",
                severity="info",
            )
        )

    if payload.execution_mode == "parallel" and len(steps) <= 1:
        warnings.append(
            TaskExecutionPreviewWarning(
                code="W_PREVIEW_PARALLEL_SINGLE_STEP",
                message="Parallel mode currently resolves to a single agent; behavior will be similar to single execution mode.",
                severity="info",
                applies_to_step=steps[0].step if steps else None,
            )
        )

    if payload.execution_mode == "pipeline" and len(steps) <= 1:
        warnings.append(
            TaskExecutionPreviewWarning(
                code="W_PREVIEW_PIPELINE_SINGLE_STEP",
                message="Pipeline mode currently resolves to a single step; behavior will be similar to single execution mode.",
                severity="info",
                applies_to_step=steps[0].step if steps else None,
            )
        )

    return warnings


def normalize_arbitration(value: str | None, default: str = "off") -> str:
    return normalize_arbitration_mode(value, default=default)


