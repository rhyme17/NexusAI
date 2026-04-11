from pathlib import Path
import sys
from typing import cast

from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.main import app
from backend.app.api import auth as auth_api
from backend.app.api import tasks as tasks_api
from backend.app.services.auth_service import reset_auth_service
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.store import InMemoryStore


client = TestClient(app)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "change-me-admin-password"


def _bootstrap_admin_and_headers(monkeypatch, tmp_path: Path) -> dict[str, str]:
    monkeypatch.setenv("NEXUSAI_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    reset_auth_service()
    login = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_user_and_headers(admin_headers: dict[str, str], username: str, password: str = "password123") -> dict[str, object]:
    invite_response = client.post(
        "/api/auth/invites",
        json={"max_uses": 1, "expires_hours": 24},
        headers=admin_headers,
    )
    assert invite_response.status_code == 200
    invite_code = invite_response.json()["code"]

    register = client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "invite_code": invite_code},
    )
    assert register.status_code == 200
    login = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    body = login.json()
    return {
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
        "user_id": body["user"]["user_id"],
    }


def test_task_websocket_receives_status_and_result_events() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "prepare project update", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
        patch_response = client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "completed",
                "progress": 100,
                "result": {"summary": "done"},
            },
        )
        assert patch_response.status_code == 200

        event_types = {websocket.receive_json()["type"] for _ in range(3)}

    assert "TaskUpdate" in event_types
    assert "TaskResult" in event_types
    assert "TaskComplete" in event_types


def test_task_websocket_receives_conflict_and_decision_events() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "choose report strategy", "priority": "high"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
        first_patch = client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "in_progress",
                "progress": 50,
                "agent_id": "agent_research",
                "confidence": 0.55,
                "result": {"summary": "strategy A"},
            },
        )
        assert first_patch.status_code == 200

        second_patch = client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "completed",
                "progress": 100,
                "agent_id": "agent_writer",
                "confidence": 0.92,
                "result": {"summary": "strategy B"},
            },
        )
        assert second_patch.status_code == 200

        event_types = {websocket.receive_json()["type"] for _ in range(9)}

    assert "ConflictNotice" in event_types
    assert "Decision" in event_types
    assert "Vote" in event_types
    assert "TaskComplete" in event_types


def test_task_websocket_receives_failed_terminal_event() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "trigger failure event", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
        patch_response = client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "failed",
                "progress": 75,
                "error_code": "E_WORKER",
                "error_message": "worker crashed",
                "result": {"error": "worker crashed"},
            },
        )
        assert patch_response.status_code == 200

        events = [websocket.receive_json() for _ in range(3)]

    event_types = {event["type"] for event in events}
    failed_event = next(event for event in events if event["type"] == "TaskFailed")

    assert "TaskUpdate" in event_types
    assert "TaskResult" in event_types
    assert "TaskFailed" in event_types
    assert failed_event["payload"]["error_code"] == "E_WORKER"
    assert failed_event["payload"]["error_message"] == "worker crashed"


def test_task_websocket_receives_claim_and_handoff_events() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "simulate claim handoff stream", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
        simulate_response = client.post(
            f"/api/tasks/{task_id}/simulate",
            json={"mode": "success", "simulate_handoff": True},
        )
        assert simulate_response.status_code == 200

        event_types = {websocket.receive_json()["type"] for _ in range(8)}

    assert "TaskClaim" in event_types
    assert "TaskHandoff" in event_types
    assert "TaskComplete" in event_types


def test_task_websocket_receives_retry_event_after_failure() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "retry websocket flow", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
        fail_response = client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "failed",
                "progress": 100,
                "error_code": "E_FAIL",
                "error_message": "simulated fail",
                "result": {"error": "simulated fail"},
            },
        )
        assert fail_response.status_code == 200

        retry_response = client.post(
            f"/api/tasks/{task_id}/retry",
            json={"reason": "try again", "requeue": False},
        )
        assert retry_response.status_code == 200

        event_types = {websocket.receive_json()["type"] for _ in range(4)}

    assert "TaskFailed" in event_types
    assert "TaskRetry" in event_types


def test_task_websocket_receives_retry_exhausted_event() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "retry exhausted websocket", "priority": "low", "metadata": {"max_retries": 0}},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
        fail_response = client.patch(
            f"/api/tasks/{task_id}/status",
            json={"status": "failed", "progress": 100, "result": {"error": "no retry"}},
        )
        assert fail_response.status_code == 200

        retry_response = client.post(f"/api/tasks/{task_id}/retry", json={"requeue": False})
        assert retry_response.status_code == 409

        event_types = {websocket.receive_json()["type"] for _ in range(4)}

    assert "TaskFailed" in event_types
    assert "TaskRetryExhausted" in event_types


def test_task_websocket_receives_pipeline_execution_events() -> None:
    class FakeExecutionService:
        def execute(self, **kwargs: object):
            agent = kwargs["agent"]
            agent_id = getattr(agent, "agent_id") if agent is not None else "unknown"

            class Result:
                confidence = 0.8
                metrics = {"latency_ms": 6, "usage": {"total_tokens": 18}}
                result = {
                    "summary": f"pipeline summary from {agent_id}",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 6, "usage": {"total_tokens": 18}},
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "websocket pipeline events", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
            execute_response = client.post(
                f"/api/tasks/{task_id}/execute",
                json={
                    "execution_mode": "pipeline",
                    "pipeline_agent_ids": ["agent_planner", "agent_research"],
                },
            )
            assert execute_response.status_code == 200

            events = [websocket.receive_json() for _ in range(12)]

        event_types = {event["type"] for event in events}
        assert "TaskPipelineStart" in event_types
        assert "AgentExecutionStart" in event_types
        assert "AgentExecutionResult" in event_types
        assert "TaskPipelineFinish" in event_types
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_task_websocket_receives_parallel_execution_events() -> None:
    class FakeExecutionService:
        def execute(self, **kwargs: object):
            agent = kwargs["agent"]
            agent_id = getattr(agent, "agent_id") if agent is not None else "unknown"

            class Result:
                confidence = 0.75
                metrics = {"latency_ms": 6, "usage": {"total_tokens": 16}}
                result = {
                    "summary": f"parallel summary from {agent_id}",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 6, "usage": {"total_tokens": 16}},
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "websocket parallel events", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        with client.websocket_connect(f"/ws/tasks/{task_id}") as websocket:
            execute_response = client.post(
                f"/api/tasks/{task_id}/execute",
                json={
                    "execution_mode": "parallel",
                    "pipeline_agent_ids": ["agent_research", "agent_writer"],
                    "allow_fallback": False,
                },
            )
            assert execute_response.status_code == 200

            events = [websocket.receive_json() for _ in range(8)]

        event_types = {event["type"] for event in events}
        assert event_types.intersection({"TaskUpdate", "AgentExecutionStart", "TaskClaim"})
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_task_websocket_requires_auth_when_api_auth_enabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key")

    create_response = client.post(
        "/api/tasks",
        json={"objective": "ws auth required", "priority": "medium"},
        headers={"X-API-Key": "viewer-key"},
    )
    assert create_response.status_code == 201
    task_id = create_response.json()["task_id"]

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/tasks/{task_id}"):
            pass


def test_task_websocket_hides_non_owner_task_when_api_auth_enabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key")

    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[tasks_api.get_message_bus] = lambda: bus
    app.dependency_overrides[auth_api.get_store] = lambda: store
    app.dependency_overrides[auth_api.get_message_bus] = lambda: bus
    try:
        owner = _create_user_and_headers(admin_headers, "ws-owner")
        other = _create_user_and_headers(admin_headers, "ws-other")

        create_response = client.post(
            "/api/tasks",
            json={"objective": "ws ownership", "priority": "medium"},
            headers=cast(dict[str, str], owner["headers"]),
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/ws/tasks/{task_id}",
                headers=cast(dict[str, str], other["headers"]),
            ):
                pass
    finally:
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(tasks_api.get_message_bus, None)
        app.dependency_overrides.pop(auth_api.get_store, None)
        app.dependency_overrides.pop(auth_api.get_message_bus, None)






