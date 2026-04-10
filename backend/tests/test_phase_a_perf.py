from __future__ import annotations

from pathlib import Path
import sys
import time
from typing import Any, cast

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.main import app
from backend.app.api import tasks as tasks_api
from backend.app.models.task import TaskCreate, TaskPriority
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.migration import export_runtime_snapshot, import_runtime_snapshot
from backend.app.services.router import TaskRouter
from backend.app.services.store import InMemoryStore
from backend.app.services.workflow import WorkflowService


client = TestClient(app)


def _override_task_dependencies() -> tuple[InMemoryStore, InMemoryMessageBus]:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[tasks_api.get_message_bus] = lambda: bus
    return store, bus


def _clear_task_dependency_overrides() -> None:
    app.dependency_overrides.pop(tasks_api.get_store, None)
    app.dependency_overrides.pop(tasks_api.get_message_bus, None)


def test_phase_a_health_latency_budget(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "false")
    samples = 80
    started = time.perf_counter()
    for _ in range(samples):
        response = client.get("/health")
        assert response.status_code == 200
    elapsed_ms = (time.perf_counter() - started) * 1000
    avg_ms = elapsed_ms / samples
    # Loose guardrail to catch obvious regressions while staying stable in CI/dev machines.
    assert avg_ms < 25


def test_phase_a_task_create_latency_budget(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "false")
    _override_task_dependencies()
    samples = 24
    try:
        started = time.perf_counter()
        for idx in range(samples):
            response = client.post(
                "/api/tasks",
                json={"objective": f"phase-a perf task {idx}", "priority": "low"},
            )
            assert response.status_code == 201
        elapsed_ms = (time.perf_counter() - started) * 1000
        avg_ms = elapsed_ms / samples
        assert avg_ms < 120
    finally:
        _clear_task_dependency_overrides()


def test_phase_a_task_create_with_auth_latency_budget(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "perf-ops-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "perf-ops-key:operator")
    _override_task_dependencies()
    samples = 24
    try:
        started = time.perf_counter()
        for idx in range(samples):
            response = client.post(
                "/api/tasks",
                json={"objective": f"phase-a auth perf task {idx}", "priority": "low"},
                headers={"X-API-Key": "perf-ops-key"},
            )
            assert response.status_code == 201
        elapsed_ms = (time.perf_counter() - started) * 1000
        avg_ms = elapsed_ms / samples
        assert avg_ms < 150
    finally:
        _clear_task_dependency_overrides()


def test_phase_a_task_events_with_auth_latency_budget(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "perf-viewer-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "perf-viewer-key:viewer")
    _override_task_dependencies()
    try:
        create_response = client.post(
            "/api/tasks",
            json={"objective": "phase-a auth events perf task", "priority": "low"},
            headers={"X-API-Key": "perf-viewer-key"},
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        samples = 40
        started = time.perf_counter()
        for _ in range(samples):
            response = client.get(
                f"/api/tasks/{task_id}/events",
                headers={"X-API-Key": "perf-viewer-key"},
            )
            assert response.status_code == 200
        elapsed_ms = (time.perf_counter() - started) * 1000
        avg_ms = elapsed_ms / samples
        assert avg_ms < 45
    finally:
        _clear_task_dependency_overrides()


def test_phase_a_task_list_in_read_only_latency_budget(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "perf-viewer-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "perf-viewer-key:viewer")
    monkeypatch.setenv("NEXUSAI_READ_ONLY_MODE", "true")
    _override_task_dependencies()
    try:
        samples = 40
        started = time.perf_counter()
        for _ in range(samples):
            response = client.get("/api/tasks", headers={"X-API-Key": "perf-viewer-key"})
            assert response.status_code == 200
        elapsed_ms = (time.perf_counter() - started) * 1000
        avg_ms = elapsed_ms / samples
        assert avg_ms < 35
    finally:
        _clear_task_dependency_overrides()


def test_phase_b_workflow_dag_generation_latency_budget() -> None:
    workflow = WorkflowService(store=InMemoryStore(persistence_enabled=False), router=TaskRouter(), bus=InMemoryMessageBus(persistence_enabled=False))
    samples = 120
    started = time.perf_counter()
    for _ in range(samples):
        decomposition = workflow._build_decomposition(
            objective="research implementation plan with review and final summary",
            assigned_agent_ids=["agent_planner", "agent_research", "agent_writer"],
            metadata={"decomposition_template": "planning"},
        )
        workflow_run = cast(dict[str, Any], decomposition["workflow_run"])
        dag_nodes = cast(list[dict[str, Any]], decomposition["dag_nodes"])
        assert workflow_run["node_count"] == len(dag_nodes)
    elapsed_ms = (time.perf_counter() - started) * 1000
    avg_ms = elapsed_ms / samples
    assert avg_ms < 3


def test_phase_b_workflow_scheduler_cycle_latency_budget() -> None:
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=store, router=TaskRouter(), bus=bus)
    samples = 40
    started = time.perf_counter()
    for idx in range(samples):
        task = store.create_task(TaskCreate(objective=f"scheduler perf task {idx}", priority=TaskPriority.LOW))
        workflow.enqueue_task(task.task_id)
        workflow.complete_node(task.task_id, node_id="step_1")
        workflow.complete_node(task.task_id, node_id="step_2")
        workflow.complete_node(task.task_id, node_id="step_3")
        workflow.complete_node(task.task_id, node_id="step_4")
    elapsed_ms = (time.perf_counter() - started) * 1000
    avg_ms = elapsed_ms / samples
    assert avg_ms < 12


def test_phase_b_snapshot_migration_latency_budget() -> None:
    source_store = InMemoryStore(persistence_enabled=False)
    source_bus = InMemoryMessageBus(persistence_enabled=False)
    workflow = WorkflowService(store=source_store, router=TaskRouter(), bus=source_bus)
    for idx in range(20):
        task = source_store.create_task(TaskCreate(objective=f"migration perf {idx}", priority=TaskPriority.LOW))
        workflow.enqueue_task(task.task_id)
        workflow.complete_node(task.task_id, node_id="step_1")

    target_store = InMemoryStore(persistence_enabled=False)
    target_bus = InMemoryMessageBus(persistence_enabled=False)
    started = time.perf_counter()
    snapshot = export_runtime_snapshot(store=source_store, bus=source_bus)
    result = import_runtime_snapshot(snapshot, store=target_store, bus=target_bus)
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert result["matches"] is True
    assert elapsed_ms < 40


