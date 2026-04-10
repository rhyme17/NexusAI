from pathlib import Path
import json
import sys
from typing import Any, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import HTTPException

from backend.app.models.agent import Agent, AgentRegister, AgentStatus
from backend.app.models.message import MessageType
from backend.app.models.task import TaskCreate, TaskExecutionRequest, TaskPriority, TaskProposal, TaskStatus, TaskStatusUpdate, TaskRetryRequest
from backend.app.services.agent_execution import AgentExecutionError, AgentExecutionService
from backend.app.services.consensus import ConsensusService
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.router import TaskRouter
from backend.app.services.store import InMemoryStore
from backend.app.services.task_execution_coordinator import TaskExecutionCoordinator
from backend.app.services.task_status_service import TaskStatusService
from backend.app.services.workflow import WorkflowService


_CONFLICT_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "conflict_samples.json"


class _FailingExecutionService(AgentExecutionService):
    def execute(self, **_: object):
        raise AgentExecutionError("E_EXECUTION_PROVIDER", "provider unavailable")


class _LongSummaryExecutionService(AgentExecutionService):
    def execute(self, **_: object):
        long_summary = f"DeepSeek event summary {'X' * 900}"

        class _Result:
            confidence = 0.93
            result = {
                "summary": long_summary,
                "mode": "real",
                "provider": "openai_compatible",
            }
            metrics = {"latency_ms": 14, "usage": {"total_tokens": 456}}

        return _Result()


def test_task_status_service_claim_and_handoff_publish_events() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    service = TaskStatusService(store=store, bus=bus)

    task = store.create_task(TaskCreate(objective="service claim handoff", priority=TaskPriority.MEDIUM))

    service.claim_task(task_id=task.task_id, agent_id="agent_planner", note="owning task")
    service.handoff_task(
        task_id=task.task_id,
        from_agent_id="agent_planner",
        to_agent_id="agent_research",
        reason="needs deeper lookup",
    )

    events, _ = bus.list_task_events(task.task_id, limit=10)
    event_types = [event.type for event in events]
    assert event_types[-2:] == [MessageType.TASK_CLAIM, MessageType.TASK_HANDOFF]


def test_task_execution_coordinator_retry_exhausted_emits_event() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    status_service = TaskStatusService(store=store, bus=bus)
    coordinator = TaskExecutionCoordinator(
        store=store,
        status_service=status_service,
        consensus_service=ConsensusService(),
        execution_service=_FailingExecutionService(),
    )
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(
        TaskCreate(
            objective="retry exhausted service path",
            priority=TaskPriority.MEDIUM,
            metadata={"max_retries": 0},
        )
    )
    status_service.apply_status_update(
        task.task_id,
        TaskStatusUpdate(
            status=TaskStatus.FAILED,
            progress=100,
            error_message="failed once",
        ),
        ConsensusService(),
    )

    with pytest.raises(HTTPException) as exc:
        coordinator.retry_task(task_id=task.task_id, payload=TaskRetryRequest(requeue=False), workflow=workflow)

    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail["error_code"] == "E_TASK_RETRY_EXHAUSTED"
    assert detail["max_retries"] == 0

    exhausted_events, _ = bus.list_task_events(task.task_id, event_types=[MessageType.TASK_RETRY_EXHAUSTED], limit=10)
    assert len(exhausted_events) == 1
    assert exhausted_events[0].payload["max_retries"] == 0


def test_task_execution_coordinator_preserves_full_execution_summary_in_events() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    status_service = TaskStatusService(store=store, bus=bus)
    coordinator = TaskExecutionCoordinator(
        store=store,
        status_service=status_service,
        consensus_service=ConsensusService(),
        execution_service=_LongSummaryExecutionService(),
    )

    agent = store.register_agent(AgentRegister(name="planner-agent", role="planner", skills=["plan"]))
    task = store.create_task(TaskCreate(objective="full summary execution", priority=TaskPriority.MEDIUM))
    store.assign_workflow_context(task.task_id, assigned_agent_ids=[agent.agent_id], decomposition={"mode": "mvp_linear", "subtasks": []})

    updated = coordinator.execute_task(task_id=task.task_id, payload=TaskExecutionRequest(agent_id=agent.agent_id))
    assert updated.result is not None

    events, _ = bus.list_task_events(task.task_id, event_types=[MessageType.AGENT_EXECUTION_RESULT], limit=10)
    assert len(events) == 1
    summary = str(events[0].payload["summary"])
    assert summary.startswith("DeepSeek event summary")
    assert len(summary) > 500


def test_task_router_route_task_returns_explanation_and_prefers_available_agent() -> None:
    router = TaskRouter()
    store = InMemoryStore(persistence_enabled=False)
    task = store.create_task(TaskCreate(objective="research synthesis brief", priority=TaskPriority.MEDIUM))

    agents = [
        Agent(
            agent_id="agent_online_light",
            name="online-light",
            role="research",
            skills=["research", "analysis"],
            status=AgentStatus.ONLINE,
            metadata={"active_task_count": 0},
        ),
        Agent(
            agent_id="agent_busy_heavy",
            name="busy-heavy",
            role="research",
            skills=["research", "analysis"],
            status=AgentStatus.BUSY,
            metadata={"active_task_count": 5},
        ),
        Agent(
            agent_id="agent_offline",
            name="offline-agent",
            role="research",
            skills=["research", "analysis"],
            status=AgentStatus.OFFLINE,
            metadata={"active_task_count": 0},
        ),
    ]

    selected, explanation = router.route_task(task, agents, limit=2)

    assert selected[0] == "agent_online_light"
    assert explanation["selected_agent_ids"] == selected
    assert explanation["strategy"] == "keyword_skill_status_load"
    assert explanation["policy"]["policy_version"] == "v1"
    assert explanation["priority"] == "medium"
    assert explanation["candidates"][0]["agent_id"] == "agent_online_light"
    assert "score_breakdown" in explanation["candidates"][0]
    assert "status=online" in explanation["candidates"][0]["selection_reason"]


def test_task_router_is_deterministic_for_same_input_snapshot() -> None:
    router = TaskRouter()
    store = InMemoryStore(persistence_enabled=False)
    task = store.create_task(TaskCreate(objective="research synthesis brief", priority=TaskPriority.HIGH))
    agents = [
        Agent(
            agent_id="agent_b",
            name="b",
            role="research",
            skills=["research"],
            status=AgentStatus.ONLINE,
            metadata={"active_task_count": 1},
        ),
        Agent(
            agent_id="agent_a",
            name="a",
            role="research",
            skills=["research"],
            status=AgentStatus.ONLINE,
            metadata={"active_task_count": 1},
        ),
    ]

    observed = [tuple(router.route_task(task, agents, limit=2)[0]) for _ in range(20)]
    assert all(item == observed[0] for item in observed)


def test_task_router_load_penalty_metadata_override_changes_ranking() -> None:
    router = TaskRouter()
    store = InMemoryStore(persistence_enabled=False)
    agents = [
        Agent(
            agent_id="agent_online_heavy",
            name="online-heavy",
            role="research",
            skills=["research"],
            status=AgentStatus.ONLINE,
            metadata={"active_task_count": 20},
        ),
        Agent(
            agent_id="agent_busy_light",
            name="busy-light",
            role="research",
            skills=["research"],
            status=AgentStatus.BUSY,
            metadata={"active_task_count": 0},
        ),
    ]

    baseline_task = store.create_task(TaskCreate(objective="research routing", priority=TaskPriority.HIGH))
    selected_baseline, _ = router.route_task(baseline_task, agents, limit=1)

    override_task = store.create_task(
        TaskCreate(
            objective="research routing",
            priority=TaskPriority.HIGH,
            metadata={"routing_policy": {"load_penalty": 0}},
        )
    )
    selected_override, explanation_override = router.route_task(override_task, agents, limit=1)

    assert selected_baseline == ["agent_busy_light"]
    assert selected_override == ["agent_online_heavy"]
    assert explanation_override["policy"]["load_penalty"] == 0


def test_workflow_service_builds_minimal_dag_queue_metadata() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    decomposition = workflow._build_decomposition(
        objective="research implementation plan",
        assigned_agent_ids=["agent_planner", "agent_research", "agent_writer"],
        metadata={"decomposition_template": "planning"},
    )
    workflow_run = cast(dict[str, Any], decomposition["workflow_run"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    dag_edges = cast(list[dict[str, Any]], decomposition["dag_edges"])

    assert workflow_run["scheduler_mode"] == "mvp_linear_queue"
    assert workflow_run["node_count"] == len(dag_nodes)
    assert decomposition["ready_queue"] == ["step_1"]
    assert dag_nodes[0]["dispatch_state"] == "ready"
    assert dag_nodes[1]["dispatch_state"] == "blocked"
    assert dag_edges[0]["from_node_id"] == "step_1"
    assert dag_edges[0]["to_node_id"] == "step_2"


def test_workflow_service_enqueue_dispatches_first_ready_node_and_claims_owner() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(TaskCreate(objective="research execution queue", priority=TaskPriority.MEDIUM))

    workflow.enqueue_task(task.task_id)

    updated = store.get_task(task.task_id)
    assert updated is not None
    decomposition = cast(dict[str, Any], updated.metadata["decomposition"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    assert updated.current_agent_id == dag_nodes[0]["assigned_agent_id"]
    assert dag_nodes[0]["dispatch_state"] == "running"
    assert decomposition["ready_queue"] == []
    assert decomposition["dispatch_state"]["running_count"] == 1

    events, _ = bus.list_task_events(task.task_id, limit=20)
    event_types = [event.type for event in events]
    assert MessageType.TASK_PIPELINE_START in event_types
    assert MessageType.TASK_CLAIM in event_types


def test_workflow_service_complete_node_unblocks_and_dispatches_next_node() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(
        TaskCreate(
            objective="planning handoff workflow",
            priority=TaskPriority.MEDIUM,
            metadata={"decomposition_template": "planning"},
        )
    )

    workflow.enqueue_task(task.task_id)
    workflow.complete_node(task.task_id, node_id="step_1", result={"summary": "step one done"})

    updated = store.get_task(task.task_id)
    assert updated is not None
    decomposition = cast(dict[str, Any], updated.metadata["decomposition"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    assert dag_nodes[0]["dispatch_state"] == "completed"
    assert dag_nodes[1]["dispatch_state"] == "running"
    assert decomposition["dispatch_state"]["completed_count"] == 1
    assert decomposition["dispatch_state"]["running_count"] == 1

    events, _ = bus.list_task_events(task.task_id, limit=20)
    handoff_events = [event for event in events if event.type == MessageType.TASK_HANDOFF]
    assert handoff_events
    assert handoff_events[-1].payload["to_agent_id"] == dag_nodes[1]["assigned_agent_id"]


def test_workflow_service_fail_and_requeue_resets_failed_node_and_dispatches_again() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(TaskCreate(objective="retryable queue workflow", priority=TaskPriority.MEDIUM))

    workflow.enqueue_task(task.task_id)
    workflow.fail_node(task.task_id, node_id="step_1", error_code="E_NODE", error_message="node failed")
    workflow.requeue_task(task.task_id, reason="manual retry")

    updated = store.get_task(task.task_id)
    assert updated is not None
    decomposition = cast(dict[str, Any], updated.metadata["decomposition"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    assert dag_nodes[0]["dispatch_state"] == "running"
    assert dag_nodes[0]["attempt_count"] == 2
    assert decomposition["dispatch_state"]["failed_count"] == 0
    assert decomposition["dispatch_state"]["running_count"] == 1

    events, _ = bus.list_task_events(task.task_id, limit=30)
    requeue_updates = [event for event in events if event.type == MessageType.TASK_UPDATE and event.payload.get("workflow_event") == "task_requeued"]
    assert requeue_updates


def test_workflow_service_parallel_branches_dispatch_multiple_ready_nodes() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(
        TaskCreate(
            objective="research and review with synthesis",
            priority=TaskPriority.HIGH,
            metadata={"workflow_parallel_branches": True},
        )
    )

    workflow.enqueue_task(task.task_id)
    workflow.complete_node(task.task_id, node_id="step_1", result={"summary": "step one done"})

    updated = store.get_task(task.task_id)
    assert updated is not None
    decomposition = cast(dict[str, Any], updated.metadata["decomposition"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    step_2 = next(node for node in dag_nodes if node["node_id"] == "step_2")
    step_3 = next(node for node in dag_nodes if node["node_id"] == "step_3")
    assert decomposition["parallel_branches_enabled"] is True
    assert step_2["dispatch_state"] == "running"
    assert step_3["dispatch_state"] == "running"
    assert decomposition["dispatch_state"]["running_count"] == 2


def test_workflow_service_requeue_is_idempotent_when_no_failed_node() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(TaskCreate(objective="idempotent requeue", priority=TaskPriority.MEDIUM))

    workflow.enqueue_task(task.task_id)
    before = store.get_task(task.task_id)
    assert before is not None
    before_decomposition = cast(dict[str, Any], before.metadata["decomposition"])
    before_attempt = int(cast(list[dict[str, Any]], before_decomposition["dag_nodes"])[0]["attempt_count"])

    workflow.requeue_task(task.task_id, reason="duplicate click")

    after = store.get_task(task.task_id)
    assert after is not None
    after_decomposition = cast(dict[str, Any], after.metadata["decomposition"])
    after_attempt = int(cast(list[dict[str, Any]], after_decomposition["dag_nodes"])[0]["attempt_count"])
    assert after_attempt == before_attempt

    events, _ = bus.list_task_events(task.task_id, limit=30)
    skipped = [
        event
        for event in events
        if event.type == MessageType.TASK_UPDATE and event.payload.get("workflow_event") == "task_requeue_skipped"
    ]
    assert skipped


def test_workflow_service_fail_fast_keeps_blocked_nodes_after_failure() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(
        TaskCreate(
            objective="fail fast workflow policy",
            priority=TaskPriority.HIGH,
            metadata={"workflow_parallel_branches": True, "workflow_failure_policy": "fail_fast"},
        )
    )
    workflow.enqueue_task(task.task_id)
    workflow.fail_node(task.task_id, node_id="step_1", error_code="E_STEP", error_message="boom")

    updated = store.get_task(task.task_id)
    assert updated is not None
    decomposition = cast(dict[str, Any], updated.metadata["decomposition"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    step_2 = next(node for node in dag_nodes if node["node_id"] == "step_2")
    step_3 = next(node for node in dag_nodes if node["node_id"] == "step_3")
    assert decomposition["failure_policy"] == "fail_fast"
    assert step_2["dispatch_state"] == "blocked"
    assert step_3["dispatch_state"] == "blocked"

    events, _ = bus.list_task_events(task.task_id, limit=20)
    failure_events = [
        event for event in events if event.type == MessageType.TASK_UPDATE and event.payload.get("workflow_event") == "node_failed"
    ]
    assert failure_events
    assert failure_events[-1].payload["failure_policy"] == "fail_fast"


def test_workflow_service_continue_unblocks_and_dispatches_after_failure() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(
        TaskCreate(
            objective="continue workflow policy",
            priority=TaskPriority.HIGH,
            metadata={"workflow_parallel_branches": True, "workflow_failure_policy": "continue"},
        )
    )
    workflow.enqueue_task(task.task_id)
    workflow.fail_node(task.task_id, node_id="step_1", error_code="E_STEP", error_message="boom")

    updated = store.get_task(task.task_id)
    assert updated is not None
    decomposition = cast(dict[str, Any], updated.metadata["decomposition"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    step_2 = next(node for node in dag_nodes if node["node_id"] == "step_2")
    step_3 = next(node for node in dag_nodes if node["node_id"] == "step_3")
    assert decomposition["failure_policy"] == "continue"
    assert step_2["dispatch_state"] == "running"
    assert step_3["dispatch_state"] == "running"

    events, _ = bus.list_task_events(task.task_id, limit=40)
    workflow_events = [
        event.payload.get("workflow_event")
        for event in events
        if event.type == MessageType.TASK_UPDATE and isinstance(event.payload.get("workflow_event"), str)
    ]
    assert "node_failed" in workflow_events
    assert "node_dispatched" in workflow_events
    failed_index = workflow_events.index("node_failed")
    assert "node_dispatched" in workflow_events[failed_index + 1 :]


@pytest.mark.parametrize("sample", json.loads(_CONFLICT_FIXTURE_PATH.read_text(encoding="utf-8")))
def test_consensus_explanation_stays_structured_for_conflict_samples(sample: dict[str, Any]) -> None:
    store = InMemoryStore(persistence_enabled=False)
    task = store.create_task(TaskCreate(objective=f"consensus sample {sample['name']}", priority=TaskPriority.MEDIUM))

    task.proposals = [
        TaskProposal(
            agent_id=item["agent_id"],
            result={"summary": item["summary"]},
            confidence=float(item["confidence"]),
        )
        for item in sample["proposals"]
    ]

    consensus = ConsensusService().evaluate(task, strategy=sample["strategy"])

    assert consensus is not None
    assert consensus.decided_by == sample["expected"]["decided_by"]
    assert consensus.conflict_detected is sample["expected"]["conflict_detected"]
    assert isinstance(consensus.explanation, dict)
    explanation = cast(dict[str, Any], consensus.explanation)
    assert {
        "strategy",
        "proposal_count",
        "unique_view_count",
        "selected_agent_id",
        "selected_confidence",
        "selected_summary",
        "comparison_basis",
        "views",
    }.issubset(explanation.keys())
    assert explanation["selected_agent_id"] == sample["expected"]["selected_agent_id"]
    assert isinstance(explanation["views"], list)


