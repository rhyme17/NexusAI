from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.agents import build_default_agents
from backend.app.models.agent import AgentRegister
from backend.app.models.message import BusMessage, MessageType
from backend.app.models.task import TaskCreate, TaskPriority, TaskStatus, TaskStatusUpdate
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.router import TaskRouter
from backend.app.services.store import InMemoryStore
from backend.app.services.workflow import WorkflowService


def test_store_persists_tasks_and_agents_across_reloads(tmp_path: Path) -> None:
    tasks_file = tmp_path / "tasks.json"
    agents_file = tmp_path / "agents.json"

    store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tasks_file,
        agents_file=agents_file,
    )
    custom_agent = store.register_agent(
        AgentRegister(name="planner-temp", role="planner", skills=["plan", "analysis"])
    )
    task = store.create_task(TaskCreate(objective="persist task state", priority=TaskPriority.HIGH))
    store.claim_task(task.task_id, "agent_planner")
    store.update_task_status(
        task.task_id,
        TaskStatusUpdate(
            status=TaskStatus.FAILED,
            progress=100,
            error_code="E_PERSIST",
            error_message="persisted failure",
            result={"error": "persisted failure"},
        ),
    )

    reloaded_store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tasks_file,
        agents_file=agents_file,
    )
    restored_task = reloaded_store.get_task(task.task_id)

    assert restored_task is not None
    assert restored_task.status == TaskStatus.FAILED
    assert restored_task.current_agent_id == "agent_planner"
    assert restored_task.attempt_history[-1].outcome == "failed"
    assert reloaded_store.get_agent(custom_agent.agent_id) is not None


def test_store_bootstraps_missing_default_agents_without_duplicates(tmp_path: Path) -> None:
    agents_file = tmp_path / "agents.json"
    tasks_file = tmp_path / "tasks.json"
    persisted_agent = build_default_agents()[0]
    agents_file.write_text(
        json.dumps({persisted_agent.agent_id: persisted_agent.model_dump(mode="json")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tasks_file,
        agents_file=agents_file,
    )
    agent_ids = [agent.agent_id for agent in store.list_agents()]

    for default_agent in build_default_agents():
        assert default_agent.agent_id in agent_ids
    assert agent_ids.count(persisted_agent.agent_id) == 1



def test_message_bus_persists_event_history_across_reloads(tmp_path: Path) -> None:
    events_file = tmp_path / "events.json"
    bus = InMemoryMessageBus(persistence_enabled=True, events_file=events_file)
    bus.publish(
        BusMessage(
            message_id="msg_task_request",
            type=MessageType.TASK_REQUEST,
            sender="api_gateway",
            task_id="task_demo",
            payload={"objective": "persist events"},
        )
    )
    bus.publish(
        BusMessage(
            message_id="msg_task_complete",
            type=MessageType.TASK_COMPLETE,
            sender="workflow_engine",
            task_id="task_demo",
            payload={"status": "completed"},
        )
    )

    restored_bus = InMemoryMessageBus(persistence_enabled=True, events_file=events_file)
    events, total = restored_bus.list_task_events("task_demo", limit=10)

    assert total == 2
    assert [event.type for event in events] == [MessageType.TASK_REQUEST, MessageType.TASK_COMPLETE]


def test_store_loads_seed_data_when_enabled(monkeypatch, tmp_path: Path) -> None:
    seed_file = tmp_path / "seed.json"
    seed_file.write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "name": "seed-agent",
                        "role": "reviewer",
                        "skills": ["quality"],
                    }
                ],
                "tasks": [
                    {
                        "objective": "seeded objective",
                        "priority": "low",
                        "metadata": {"source": "seed"},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("NEXUSAI_SEED_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_SEED_FILE", str(seed_file))
    monkeypatch.setenv("NEXUSAI_SEED_APPLY_IF_EMPTY", "true")

    store = InMemoryStore(
        persistence_enabled=False,
        tasks_file=tmp_path / "tasks.json",
        agents_file=tmp_path / "agents.json",
    )

    assert any(task.objective == "seeded objective" for task in store.list_tasks())
    assert any(agent.name == "seed-agent" for agent in store.list_agents())


def test_store_register_agent_is_idempotent_for_same_signature(tmp_path: Path) -> None:
    store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tmp_path / "tasks.json",
        agents_file=tmp_path / "agents.json",
    )

    first = store.register_agent(AgentRegister(name="planner-1", role="planner", skills=["plan", "analysis"]))
    second = store.register_agent(AgentRegister(name="planner-1", role="planner", skills=["analysis", "plan"]))

    assert first.agent_id == second.agent_id
    assert len([agent for agent in store.list_agents() if agent.name == "planner-1" and agent.role == "planner"]) == 1


def test_store_and_bus_export_and_clear_snapshots(tmp_path: Path) -> None:
    store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tmp_path / "tasks.json",
        agents_file=tmp_path / "agents.json",
    )
    bus = InMemoryMessageBus(persistence_enabled=True, events_file=tmp_path / "events.json")

    task = store.create_task(TaskCreate(objective="clear me", priority=TaskPriority.LOW))
    bus.publish(
        BusMessage(
            message_id="msg_clear_demo",
            type=MessageType.TASK_REQUEST,
            sender="api_gateway",
            task_id=task.task_id,
            payload={"objective": "clear me"},
        )
    )

    snapshot_before = store.export_snapshot()
    events_before = bus.export_snapshot()
    assert len(snapshot_before["tasks"]) == 1
    assert len(events_before["events"]) == 1

    store.clear(keep_default_agents=True)
    bus.clear_history()

    snapshot_after = store.export_snapshot()
    events_after = bus.export_snapshot()
    assert snapshot_after["tasks"] == {}
    assert len(snapshot_after["agents"]) >= 5
    assert events_after["events"] == {}


def test_workflow_recovery_continues_dispatch_after_store_reload(tmp_path: Path) -> None:
    tasks_file = tmp_path / "tasks.json"
    agents_file = tmp_path / "agents.json"

    store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tasks_file,
        agents_file=agents_file,
    )
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(TaskCreate(objective="recovery dispatch", priority=TaskPriority.HIGH))
    workflow.enqueue_task(task.task_id)
    workflow.complete_node(task.task_id, node_id="step_1", result={"summary": "done"})

    reloaded_store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tasks_file,
        agents_file=agents_file,
    )
    reloaded_workflow = WorkflowService(store=reloaded_store, router=TaskRouter(), bus=bus)
    restored_task = reloaded_store.get_task(task.task_id)
    assert restored_task is not None

    decomposition = restored_task.metadata["decomposition"]
    nodes = decomposition["dag_nodes"]
    running_nodes = [node for node in nodes if node.get("dispatch_state") == "running"]
    assert running_nodes

    running_node_id = running_nodes[0]["node_id"]
    reloaded_workflow.complete_node(task.task_id, node_id=running_node_id, result={"summary": "continued"})

    advanced_task = reloaded_store.get_task(task.task_id)
    assert advanced_task is not None
    advanced_nodes = advanced_task.metadata["decomposition"]["dag_nodes"]
    assert any(node.get("dispatch_state") == "completed" for node in advanced_nodes)


def test_workflow_event_sequence_replay_is_stable_after_bus_reload(tmp_path: Path) -> None:
    tasks_file = tmp_path / "tasks.json"
    agents_file = tmp_path / "agents.json"
    events_file = tmp_path / "events.json"

    store = InMemoryStore(
        persistence_enabled=True,
        tasks_file=tasks_file,
        agents_file=agents_file,
    )
    bus = InMemoryMessageBus(persistence_enabled=True, events_file=events_file)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)

    task = store.create_task(
        TaskCreate(
            objective="event replay ordering",
            priority=TaskPriority.HIGH,
            metadata={"workflow_parallel_branches": True, "workflow_failure_policy": "continue"},
        )
    )
    workflow.enqueue_task(task.task_id)
    workflow.fail_node(task.task_id, node_id="step_1", error_code="E_STEP", error_message="fail once")

    restored_bus = InMemoryMessageBus(persistence_enabled=True, events_file=events_file)
    replayed, _ = restored_bus.list_task_events(task.task_id, limit=100)
    workflow_events = [
        event.payload.get("workflow_event")
        for event in replayed
        if event.type == MessageType.TASK_UPDATE and isinstance(event.payload.get("workflow_event"), str)
    ]

    assert "node_failed" in workflow_events
    assert "node_dispatched" in workflow_events
    failed_index = workflow_events.index("node_failed")
    assert "node_dispatched" in workflow_events[failed_index + 1 :]



