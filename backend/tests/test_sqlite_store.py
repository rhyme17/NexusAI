from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.api import agents as agents_api
from backend.app.api import tasks as tasks_api
from backend.app.main import app
from backend.app.models.agent import AgentRegister
from backend.app.models.task import TaskCreate, TaskPriority, TaskStatus, TaskStatusUpdate
from backend.app.services.sqlite_store import SQLiteStore


client = TestClient(app)


def test_sqlite_store_persists_tasks_and_agents_across_reloads(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "nexusai.db"

    store = SQLiteStore(sqlite_path=sqlite_path)
    custom_agent = store.register_agent(
        AgentRegister(name="sqlite-planner", role="planner", skills=["plan", "analysis"])
    )
    task = store.create_task(TaskCreate(objective="persist sqlite task state", priority=TaskPriority.HIGH))
    store.claim_task(task.task_id, "agent_planner")
    store.update_task_status(
        task.task_id,
        TaskStatusUpdate(
            status=TaskStatus.FAILED,
            progress=100,
            error_code="E_SQLITE",
            error_message="sqlite persisted failure",
        ),
    )

    reloaded_store = SQLiteStore(sqlite_path=sqlite_path)
    restored_task = reloaded_store.get_task(task.task_id)

    assert restored_task is not None
    assert restored_task.status == TaskStatus.FAILED
    assert restored_task.current_agent_id == "agent_planner"
    assert restored_task.attempt_history[-1].outcome == "failed"
    assert reloaded_store.get_agent(custom_agent.agent_id) is not None



def test_sqlite_store_clear_keeps_default_agents(tmp_path: Path) -> None:
    store = SQLiteStore(sqlite_path=tmp_path / "nexusai.db")
    task = store.create_task(TaskCreate(objective="clear sqlite snapshot", priority=TaskPriority.LOW))

    assert store.get_task(task.task_id) is not None
    assert any(agent.agent_id == "agent_planner" for agent in store.list_agents())

    store.clear(keep_default_agents=True)

    assert store.list_tasks() == []
    agent_ids = {agent.agent_id for agent in store.list_agents()}
    assert "agent_planner" in agent_ids
    assert "agent_judge" in agent_ids



def test_sqlite_store_apply_seed_data_restores_demo_content(tmp_path: Path, monkeypatch) -> None:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "objective": "sqlite seeded task",
                        "priority": "medium",
                        "metadata": {"source": "sqlite_test_seed"},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEXUSAI_SEED_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_SEED_FILE", str(seed_path))

    store = SQLiteStore(sqlite_path=tmp_path / "seeded-nexusai.db")
    store.clear(keep_default_agents=True)

    restored = store.apply_seed_data()

    assert restored is True
    assert any(task.objective == "sqlite seeded task" for task in store.list_tasks())



def test_task_api_can_run_with_sqlite_store_override(tmp_path: Path) -> None:
    sqlite_store = SQLiteStore(sqlite_path=tmp_path / "api-nexusai.db")
    app.dependency_overrides[tasks_api.get_store] = lambda: sqlite_store
    app.dependency_overrides[agents_api.get_store] = lambda: sqlite_store
    try:
        agents_response = client.get("/api/agents")
        assert agents_response.status_code == 200
        agent_ids = {agent["agent_id"] for agent in agents_response.json()}
        assert "agent_planner" in agent_ids

        task_response = client.post(
            "/api/tasks",
            json={"objective": "sqlite task api smoke", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_json = task_response.json()
        assert task_json["status"] == "in_progress"
        assert task_json["task_id"].startswith("task_")
        assert task_json["metadata"]["decomposition"]["workflow_run"]["queue_backend"] == "in_process"
        assert task_json["metadata"]["decomposition"]["ready_queue"] == []
        assert task_json["metadata"]["decomposition"]["dag_nodes"][0]["dispatch_state"] == "running"

        fetched = client.get(f"/api/tasks/{task_json['task_id']}")
        assert fetched.status_code == 200
        assert fetched.json()["objective"] == "sqlite task api smoke"

        reloaded_store = SQLiteStore(sqlite_path=tmp_path / "api-nexusai.db")
        reloaded_task = reloaded_store.get_task(task_json["task_id"])
        assert reloaded_task is not None
        decomposition = reloaded_task.metadata["decomposition"]
        assert decomposition["workflow_run"]["node_count"] == len(decomposition["dag_nodes"])
        assert decomposition["dag_nodes"][0]["dispatch_state"] == "running"
    finally:
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(agents_api.get_store, None)


def test_sqlite_store_register_agent_is_idempotent_for_same_signature(tmp_path: Path) -> None:
    store = SQLiteStore(sqlite_path=tmp_path / "dup-nexusai.db")
    first = store.register_agent(AgentRegister(name="planner-1", role="planner", skills=["plan", "analysis"]))
    second = store.register_agent(AgentRegister(name="planner-1", role="planner", skills=["analysis", "plan"]))

    assert first.agent_id == second.agent_id
    assert len([agent for agent in store.list_agents() if agent.name == "planner-1" and agent.role == "planner"]) == 1



