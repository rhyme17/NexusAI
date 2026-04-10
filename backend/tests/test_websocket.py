from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.main import app
from backend.app.api import tasks as tasks_api


client = TestClient(app)


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






