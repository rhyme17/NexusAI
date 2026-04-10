from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.models.task import TaskCreate, TaskPriority
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.migration import export_runtime_snapshot, import_runtime_snapshot, validate_runtime_snapshot
from backend.app.services.router import TaskRouter
from backend.app.services.sqlite_store import SQLiteStore
from backend.app.services.store import InMemoryStore
from backend.app.services.workflow import WorkflowService


def test_runtime_snapshot_roundtrip_preserves_workflow_state_and_events(tmp_path: Path) -> None:
    source_store = InMemoryStore(persistence_enabled=False)
    source_bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=source_store, router=TaskRouter(), bus=source_bus)

    task = source_store.create_task(
        TaskCreate(
            objective="migration roundtrip workflow",
            priority=TaskPriority.MEDIUM,
            metadata={"decomposition_template": "planning"},
        )
    )
    workflow.enqueue_task(task.task_id)
    workflow.complete_node(task.task_id, node_id="step_1", result={"summary": "done"})
    workflow.fail_node(task.task_id, node_id="step_2", error_code="E_NODE", error_message="node failed")

    snapshot = export_runtime_snapshot(store=source_store, bus=source_bus)

    target_store = SQLiteStore(sqlite_path=tmp_path / "migration-target.db")
    target_bus = InMemoryMessageBus(persistence_enabled=False)
    result = import_runtime_snapshot(snapshot, store=target_store, bus=target_bus)

    assert result["matches"] is True
    restored_task = target_store.get_task(task.task_id)
    assert restored_task is not None
    decomposition = cast(dict[str, Any], restored_task.metadata["decomposition"])
    dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
    assert decomposition["workflow_run"]["scheduler_mode"] == "mvp_linear_queue"
    assert dag_nodes[0]["dispatch_state"] == "completed"
    assert dag_nodes[1]["dispatch_state"] == "failed"
    assert dag_nodes[1]["last_error_code"] == "E_NODE"

    bus_snapshot = target_bus.export_snapshot()
    assert task.task_id in bus_snapshot["events"]
    assert len(bus_snapshot["events"][task.task_id]) == result["counts"]["events"]


def test_validate_runtime_snapshot_reports_missing_or_bad_fields() -> None:
    errors = validate_runtime_snapshot(
        {
            "tasks": {
                "task_1": {
                    "metadata": {"decomposition": {"workflow_run": "bad", "dag_nodes": "bad"}},
                    "attempt_history": "bad",
                }
            },
            "events": {"t1": "bad"},
        }
    )
    assert any("missing key: agents" in err for err in errors)
    assert any("tasks[task_1].attempt_history must be an array" in err for err in errors)
    assert any("workflow_run must be an object" in err for err in errors)
    assert any("dag_nodes must be an array" in err for err in errors)
    assert any("events[t1] must be an array" in err for err in errors)


def test_import_runtime_snapshot_rejects_invalid_snapshot_structure() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    with pytest.raises(ValueError, match="invalid snapshot"):
        import_runtime_snapshot({"tasks": {}, "agents": {}, "events": {"t1": "bad"}}, store=store, bus=bus)


