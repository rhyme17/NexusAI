from pathlib import Path
import json
import sys
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.api import agents as agents_api
from backend.app.api import debug as debug_api
from backend.app.main import app
from backend.app.api import tasks as tasks_api
from backend.app.models.task import TaskCreate, TaskPriority
from backend.app.services.agent_execution import AgentExecutionError
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.store import InMemoryStore


client = TestClient(app)
_CONFLICT_SAMPLE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "conflict_samples.json"


def test_api_auth_allows_exempt_health_without_key(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "phase-a-key")

    response = client.get("/health")
    assert response.status_code == 200


def test_api_auth_blocks_write_without_key(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "phase-a-key")

    response = client.post(
        "/api/tasks",
        json={"objective": "auth blocked write", "priority": "medium"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "E_AUTH_UNAUTHORIZED"


def test_api_auth_allows_write_with_valid_key(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "phase-a-key")

    response = client.post(
        "/api/tasks",
        json={"objective": "auth allowed write", "priority": "medium"},
        headers={"X-API-Key": "phase-a-key"},
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    ("api_key", "role"),
    [("viewer-key", "viewer"), ("operator-key", "operator")],
)
def test_api_auth_role_mapped_key_allows_general_task_write(monkeypatch, api_key: str, role: str) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key,operator-key,admin-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "viewer-key:viewer,operator-key:operator,admin-key:admin")

    response = client.post(
        "/api/tasks",
        json={"objective": f"auth role write {role}", "priority": "medium"},
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 201


def test_role_guard_blocks_non_admin_debug_clear(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key,admin-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "viewer-key:viewer,admin-key:admin")
    monkeypatch.setenv("NEXUSAI_DEBUG_API_ENABLED", "true")

    response = client.post(
        "/api/debug/storage/clear",
        headers={"X-API-Key": "viewer-key"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["error_code"] == "E_AUTH_FORBIDDEN"
    assert "admin" in detail["required_roles"]
    assert detail["actual_role"] == "viewer"


def test_role_guard_allows_admin_debug_clear(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key,admin-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "viewer-key:viewer,admin-key:admin")
    monkeypatch.setenv("NEXUSAI_DEBUG_API_ENABLED", "true")

    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[debug_api.get_store] = lambda: store
    app.dependency_overrides[debug_api.get_message_bus] = lambda: bus
    try:
        response = client.post(
            "/api/debug/storage/clear",
            headers={"X-API-Key": "admin-key"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "cleared"
    finally:
        app.dependency_overrides.pop(debug_api.get_store, None)
        app.dependency_overrides.pop(debug_api.get_message_bus, None)


def test_read_only_mode_blocks_task_create_even_with_valid_key(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "ops-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "ops-key:operator")
    monkeypatch.setenv("NEXUSAI_READ_ONLY_MODE", "true")

    response = client.post(
        "/api/tasks",
        json={"objective": "blocked by readonly", "priority": "medium"},
        headers={"X-API-Key": "ops-key"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error_code"] == "E_SYSTEM_READ_ONLY"
    assert detail["read_only"] is True


def test_read_only_mode_allows_health_and_safe_reads(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "viewer-key:viewer")
    monkeypatch.setenv("NEXUSAI_READ_ONLY_MODE", "true")

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["read_only"] is True

    list_response = client.get("/api/tasks", headers={"X-API-Key": "viewer-key"})
    assert list_response.status_code == 200


def test_audit_middleware_sets_request_id_header_and_logs_success(caplog) -> None:
    with caplog.at_level("INFO", logger="nexusai.audit"):
        response = client.get("/health", headers={"X-Request-ID": "req_phase_a_success"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req_phase_a_success"

    matching = [record for record in caplog.records if "req_phase_a_success" in record.message]
    assert matching
    payload = json.loads(matching[-1].message)
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] >= 0


def test_audit_middleware_logs_auth_failure(caplog, monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "phase-a-key")

    with caplog.at_level("INFO", logger="nexusai.audit"):
        response = client.post(
            "/api/tasks",
            json={"objective": "audit auth failure", "priority": "medium"},
        )

    assert response.status_code == 401
    payload = None
    for record in caplog.records:
        candidate = json.loads(record.message)
        if candidate.get("path") == "/api/tasks":
            payload = candidate
    assert payload is not None
    assert payload["status_code"] == 401
    assert payload["actor"] == "anonymous"


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_exposes_api_key_security_scheme() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    schemes = body["components"]["securitySchemes"]
    assert "ApiKeyAuth" in schemes
    assert schemes["ApiKeyAuth"]["name"] == "X-API-Key"


def test_openapi_marks_api_tasks_route_as_secured() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    create_task_operation = body["paths"]["/api/tasks"]["post"]
    assert create_task_operation["security"] == [{"ApiKeyAuth": []}]
    assert "401" in create_task_operation["responses"]


def test_register_agent_and_create_task() -> None:
    agent_payload = {
        "name": "planner-1",
        "role": "planner",
        "skills": ["plan", "research", "analysis"],
    }
    agent_response = client.post("/api/agents", json=agent_payload)
    assert agent_response.status_code == 201

    task_payload = {
        "objective": "research and plan a simple AI trend report",
        "priority": "high",
    }
    task_response = client.post("/api/tasks", json=task_payload)
    assert task_response.status_code == 201

    task_json = task_response.json()
    assert task_json["status"] == "in_progress"
    assert isinstance(task_json["assigned_agent_ids"], list)


def test_seeded_agents_are_available() -> None:
    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    agent_ids = {agent["agent_id"] for agent in agents}
    assert "agent_planner" in agent_ids
    assert "agent_research" in agent_ids
    assert "agent_writer" in agent_ids
    assert "agent_analyst" in agent_ids
    assert "agent_reviewer" in agent_ids
    assert "agent_judge" in agent_ids


def test_list_agents_supports_skill_and_status_filters() -> None:
    response = client.get("/api/agents?skill=review&status=online")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) >= 1
    assert all(agent["status"] == "online" for agent in agents)
    assert any("review" in " ".join(agent["skills"]).lower() for agent in agents)


def test_update_agent_status_endpoint() -> None:
    register_response = client.post(
        "/api/agents",
        json={"name": "status-agent", "role": "reviewer", "skills": ["review"]},
    )
    assert register_response.status_code == 201
    agent_id = register_response.json()["agent_id"]

    update_response = client.patch(
        f"/api/agents/{agent_id}/status",
        json={"status": "busy"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "busy"


def test_task_contains_basic_decomposition_metadata() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "research a new protocol and draft recommendations", "priority": "high"},
    )
    assert task_response.status_code == 201
    task_json = task_response.json()

    decomposition = task_json["metadata"].get("decomposition")
    assert decomposition is not None
    assert decomposition["mode"] == "mvp_linear"
    assert decomposition["template"] == "research_report"
    assert len(decomposition["subtasks"]) == 4
    assert decomposition["workflow_run"]["queue_backend"] == "in_process"
    assert decomposition["workflow_run"]["node_count"] == 4
    assert len(decomposition["dag_nodes"]) == 4
    assert len(decomposition["dag_edges"]) == 3
    assert decomposition["ready_queue"] == []
    assert decomposition["dispatch_state"]["ready_count"] == 0
    assert decomposition["dispatch_state"]["blocked_count"] == 3
    assert decomposition["dispatch_state"]["running_count"] == 1
    assert decomposition["dag_nodes"][0]["dispatch_state"] == "running"
    assert task_json["current_agent_id"] == decomposition["dag_nodes"][0]["assigned_agent_id"]

    routing = task_json["metadata"].get("routing")
    assert routing is not None
    assert routing["selected_agent_ids"] == task_json["assigned_agent_ids"]
    assert routing["strategy"] == "keyword_skill_status_load"
    assert routing["priority"] == "high"
    assert routing["policy"]["policy_version"] == "v1"
    assert "score_breakdown" in routing["candidates"][0]
    assert len(routing["candidates"]) >= len(task_json["assigned_agent_ids"])

    assigned_ids = set(task_json["assigned_agent_ids"])
    for subtask in decomposition["subtasks"]:
        assigned = subtask["assigned_agent_id"]
        assert assigned is None or assigned in assigned_ids


def test_task_decomposition_supports_template_override() -> None:
    task_response = client.post(
        "/api/tasks",
        json={
            "objective": "write a compact project summary",
            "priority": "medium",
            "metadata": {"decomposition_template": "planning"},
        },
    )
    assert task_response.status_code == 201
    decomposition = task_response.json()["metadata"]["decomposition"]
    assert decomposition["template"] == "planning"
    assert decomposition["subtasks"][0]["title"] == "Set scope and assumptions"
    assert decomposition["dag_nodes"][0]["node_id"] == "step_1"
    assert decomposition["dag_nodes"][0]["dispatch_state"] == "running"
    assert decomposition["ready_queue"] == []


def test_task_claim_and_handoff_flow() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "coordinate claim and handoff", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    claim_response = client.post(
        f"/api/tasks/{task_id}/claim",
        json={"agent_id": "agent_planner", "note": "taking ownership"},
    )
    assert claim_response.status_code == 200
    assert claim_response.json()["current_agent_id"] == "agent_planner"

    handoff_response = client.post(
        f"/api/tasks/{task_id}/handoff",
        json={
            "from_agent_id": "agent_planner",
            "to_agent_id": "agent_research",
            "reason": "needs deeper research",
        },
    )
    assert handoff_response.status_code == 200
    handoff_json = handoff_response.json()
    assert handoff_json["current_agent_id"] == "agent_research"
    assert len(handoff_json["handoff_history"]) == 1
    assert handoff_json["handoff_history"][0]["to_agent_id"] == "agent_research"

    event_types = {
        event["type"]
        for event in client.get(f"/api/tasks/{task_id}/events").json()
    }
    assert "TaskClaim" in event_types
    assert "TaskHandoff" in event_types


def test_task_claim_conflict_returns_409() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "claim conflict scenario", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    first_claim = client.post(f"/api/tasks/{task_id}/claim", json={"agent_id": "agent_planner"})
    assert first_claim.status_code == 200

    second_claim = client.post(f"/api/tasks/{task_id}/claim", json={"agent_id": "agent_writer"})
    assert second_claim.status_code == 409
    assert second_claim.json()["detail"]["error_code"] == "E_TASK_ALREADY_CLAIMED"


def test_task_claim_completed_task_returns_409() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "completed claim guard", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    complete_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "done"}},
    )
    assert complete_response.status_code == 200

    claim_response = client.post(f"/api/tasks/{task_id}/claim", json={"agent_id": "agent_planner"})
    assert claim_response.status_code == 409
    assert claim_response.json()["detail"]["error_code"] == "E_TASK_TERMINAL_CLAIM"


def test_simulate_task_success() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "simulate successful execution", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    simulate_response = client.post(
        f"/api/tasks/{task_id}/simulate",
        json={"mode": "success", "simulate_handoff": True},
    )
    assert simulate_response.status_code == 200
    simulated = simulate_response.json()
    assert simulated["status"] == "completed"
    assert simulated["progress"] == 100
    assert simulated["result"]["summary"] == "simulated execution completed"


def test_simulate_task_failure() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "simulate failed execution", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    simulate_response = client.post(
        f"/api/tasks/{task_id}/simulate",
        json={"mode": "failure", "error_message": "simulated worker timeout"},
    )
    assert simulate_response.status_code == 200
    simulated = simulate_response.json()
    assert simulated["status"] == "failed"
    assert simulated["result"]["error"] == "simulated worker timeout"

    failed_events = client.get(f"/api/tasks/{task_id}/events?type=TaskFailed").json()
    assert len(failed_events) == 1
    assert failed_events[0]["payload"]["error_message"] == "simulated worker timeout"


def test_retry_failed_task_requeues_and_emits_retry_event() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "retry failed task", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    fail_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "failed",
            "progress": 100,
            "error_code": "E_DEMO",
            "error_message": "first attempt failed",
            "result": {"error": "first attempt failed"},
        },
    )
    assert fail_response.status_code == 200

    retry_response = client.post(
        f"/api/tasks/{task_id}/retry",
        json={"reason": "retry with same plan", "requeue": True},
    )
    assert retry_response.status_code == 200
    retried = retry_response.json()
    assert retried["status"] == "in_progress"
    assert retried["retry_count"] == 1
    assert retried["result"] is None

    retry_events = client.get(f"/api/tasks/{task_id}/events?type=TaskRetry")
    assert retry_events.status_code == 200
    retry_payload = retry_events.json()[0]["payload"]
    assert retry_payload["retry_count"] == 1
    assert retry_payload["reason"] == "retry with same plan"


def test_retry_non_failed_task_returns_409() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "retry guard", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    retry_response = client.post(f"/api/tasks/{task_id}/retry", json={})
    assert retry_response.status_code == 409
    assert retry_response.json()["detail"]["error_code"] == "E_TASK_RETRY_INVALID_STATE"


def test_retry_without_requeue_keeps_task_queued() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "retry without requeue", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    fail_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "failed",
            "progress": 100,
            "result": {"error": "broken"},
        },
    )
    assert fail_response.status_code == 200

    retry_response = client.post(
        f"/api/tasks/{task_id}/retry",
        json={"requeue": False, "reason": "pause before next run"},
    )
    assert retry_response.status_code == 200
    retried = retry_response.json()
    assert retried["status"] == "queued"
    assert retried["progress"] == 0


def test_status_transition_failed_to_in_progress_requires_retry() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "transition guard failed to in_progress", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    fail_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "failed", "progress": 100, "result": {"error": "failed once"}},
    )
    assert fail_response.status_code == 200

    invalid_transition = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "in_progress", "progress": 30},
    )
    assert invalid_transition.status_code == 409
    detail = invalid_transition.json()["detail"]
    assert detail["error_code"] == "E_TASK_INVALID_STATUS_TRANSITION"
    assert detail["from_status"] == "failed"
    assert detail["to_status"] == "in_progress"


def test_status_transition_completed_to_failed_is_rejected() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "transition guard completed to failed", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    complete_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "done"}},
    )
    assert complete_response.status_code == 200

    invalid_transition = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "failed", "progress": 100, "result": {"error": "should fail"}},
    )
    assert invalid_transition.status_code == 409
    detail = invalid_transition.json()["detail"]
    assert detail["error_code"] == "E_TASK_INVALID_STATUS_TRANSITION"
    assert detail["from_status"] == "completed"
    assert detail["to_status"] == "failed"


def test_status_transition_idempotent_completed_update_is_allowed() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "idempotent completed update", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    first_complete = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "first"}},
    )
    assert first_complete.status_code == 200

    second_complete = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "second"}},
    )
    assert second_complete.status_code == 200
    assert second_complete.json()["status"] == "completed"


def test_retry_respects_max_retries_and_emits_exhausted_event() -> None:
    task_response = client.post(
        "/api/tasks",
        json={
            "objective": "retry limit demo",
            "priority": "medium",
            "metadata": {"max_retries": 1},
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    first_fail = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "failed", "progress": 100, "result": {"error": "attempt 1 failed"}},
    )
    assert first_fail.status_code == 200

    first_retry = client.post(f"/api/tasks/{task_id}/retry", json={"requeue": False, "reason": "retry once"})
    assert first_retry.status_code == 200

    second_fail = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "failed", "progress": 100, "result": {"error": "attempt 2 failed"}},
    )
    assert second_fail.status_code == 200

    blocked_retry = client.post(f"/api/tasks/{task_id}/retry", json={"requeue": False})
    assert blocked_retry.status_code == 409
    assert blocked_retry.json()["detail"]["error_code"] == "E_TASK_RETRY_EXHAUSTED"
    assert blocked_retry.json()["detail"]["max_retries"] == 1

    exhausted_events = client.get(f"/api/tasks/{task_id}/events?type=TaskRetryExhausted")
    assert exhausted_events.status_code == 200
    exhausted_payload = exhausted_events.json()[0]["payload"]
    assert exhausted_payload["max_retries"] == 1


def test_task_attempts_endpoint_returns_failure_retry_timeline() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "attempt timeline", "priority": "low", "metadata": {"max_retries": 2}},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "failed", "progress": 100, "error_message": "first fail", "result": {"error": "first fail"}},
    )
    client.post(f"/api/tasks/{task_id}/retry", json={"requeue": False, "reason": "second attempt"})
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "done"}},
    )

    attempts_response = client.get(f"/api/tasks/{task_id}/attempts")
    assert attempts_response.status_code == 200
    attempts_json = attempts_response.json()
    assert attempts_json["retry_count"] == 1
    assert attempts_json["max_retries"] == 2
    outcomes = [item["outcome"] for item in attempts_json["items"]]
    assert outcomes == ["failed", "retried", "completed"]


def test_simulate_supports_retry_success_threshold() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "threshold simulation", "priority": "medium", "metadata": {"max_retries": 3}},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    first_run = client.post(
        f"/api/tasks/{task_id}/simulate",
        json={"retry_success_threshold": 2, "error_message": "first threshold failure"},
    )
    assert first_run.status_code == 200
    assert first_run.json()["status"] == "failed"

    client.post(f"/api/tasks/{task_id}/retry", json={"requeue": False})
    second_run = client.post(
        f"/api/tasks/{task_id}/simulate",
        json={"retry_success_threshold": 2, "error_message": "second threshold failure"},
    )
    assert second_run.status_code == 200
    assert second_run.json()["status"] == "failed"

    client.post(f"/api/tasks/{task_id}/retry", json={"requeue": False})
    third_run = client.post(
        f"/api/tasks/{task_id}/simulate",
        json={"retry_success_threshold": 2},
    )
    assert third_run.status_code == 200
    assert third_run.json()["status"] == "completed"


def test_update_task_status_and_get_result() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "write a short AI newsletter", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    update_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "completed",
            "progress": 100,
            "result": {"summary": "newsletter done"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "completed"
    assert update_response.json()["progress"] == 100

    result_response = client.get(f"/api/tasks/{task_id}/result")
    assert result_response.status_code == 200
    assert result_response.json()["result"]["summary"] == "newsletter done"


def test_export_task_result_as_markdown_and_text() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "blockchain security report", "priority": "high"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    update_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "completed",
            "progress": 100,
            "result": {"summary": "# Executive Summary\n\nKey findings and recommendations."},
        },
    )
    assert update_response.status_code == 200

    markdown_response = client.get(f"/api/tasks/{task_id}/result/export?format=md")
    assert markdown_response.status_code == 200
    assert "text/markdown" in markdown_response.headers["content-type"]
    assert f"-{task_id}.md" in markdown_response.headers["content-disposition"]
    assert "## Result" in markdown_response.text

    text_response = client.get(f"/api/tasks/{task_id}/result/export?format=txt")
    assert text_response.status_code == 200
    assert "text/plain" in text_response.headers["content-type"]
    assert f"-{task_id}.txt" in text_response.headers["content-disposition"]
    assert "Task ID:" in text_response.text


def test_unknown_task_returns_404() -> None:
    status_response = client.patch(
        "/api/tasks/task_missing/status",
        json={"status": "failed", "progress": 100},
    )
    assert status_response.status_code == 404

    result_response = client.get("/api/tasks/task_missing/result")
    assert result_response.status_code == 404


def test_execute_task_missing_agent_returns_structured_404() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "execute missing agent", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    execute_response = client.post(
        f"/api/tasks/{task_id}/execute",
        json={"agent_id": "agent_missing"},
    )
    assert execute_response.status_code == 404
    detail = execute_response.json()["detail"]
    assert detail["error_code"] == "E_AGENT_NOT_FOUND"
    assert detail["agent_id"] == "agent_missing"


def test_debug_clear_restore_seed_recovers_demo_snapshot(tmp_path: Path, monkeypatch) -> None:
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "agents": [
                    {
                        "name": "seeded-reviewer",
                        "role": "reviewer",
                        "skills": ["quality", "risk"],
                    }
                ],
                "tasks": [
                    {
                        "objective": "restored from seed",
                        "priority": "medium",
                        "metadata": {"source": "api_debug_seed"},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEXUSAI_DEBUG_API_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_SEED_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_SEED_FILE", str(seed_path))

    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    store.create_task(TaskCreate(objective="ephemeral task", priority=TaskPriority.LOW))

    app.dependency_overrides[debug_api.get_store] = lambda: store
    app.dependency_overrides[debug_api.get_message_bus] = lambda: bus
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[agents_api.get_store] = lambda: store
    try:
        clear_response = client.post("/api/debug/storage/clear?restore_seed=true")
        assert clear_response.status_code == 200
        body = clear_response.json()
        assert body["seed_restored"] is True
        assert body["counts"]["tasks"] >= 1
        assert any(task.objective == "restored from seed" for task in store.list_tasks())
    finally:
        app.dependency_overrides.pop(debug_api.get_store, None)
        app.dependency_overrides.pop(debug_api.get_message_bus, None)
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(agents_api.get_store, None)


def test_conflict_detection_and_consensus_decision() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "produce architecture recommendation", "priority": "high"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    first_proposal = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 60,
            "agent_id": "agent_research",
            "confidence": 0.6,
            "result": {"summary": "Use architecture option A"},
        },
    )
    assert first_proposal.status_code == 200

    second_proposal = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "completed",
            "progress": 100,
            "agent_id": "agent_writer",
            "confidence": 0.9,
            "result": {"summary": "Use architecture option B"},
        },
    )
    assert second_proposal.status_code == 200

    task_snapshot = client.get(f"/api/tasks/{task_id}")
    assert task_snapshot.status_code == 200
    task_json = task_snapshot.json()
    assert task_json["consensus"]["conflict_detected"] is True
    assert task_json["result"]["summary"] == "Use architecture option B"
    assert task_json["consensus"]["explanation"]["selected_agent_id"] == "agent_writer"
    assert "agent_research" in task_json["consensus"]["explanation"]["conflicting_agent_ids"]

    consensus_snapshot = client.get(f"/api/tasks/{task_id}/consensus")
    assert consensus_snapshot.status_code == 200
    consensus_json = consensus_snapshot.json()
    assert len(consensus_json["proposals"]) == 2
    assert consensus_json["consensus"]["decision_result"]["summary"] == "Use architecture option B"
    assert consensus_json["consensus"]["explanation"]["comparison_basis"] == "highest confidence"


def test_majority_vote_strategy_prefers_most_common_view() -> None:
    task_response = client.post(
        "/api/tasks",
        json={
            "objective": "decide launch plan",
            "priority": "high",
            "metadata": {"consensus_strategy": "majority_vote"},
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 40,
            "agent_id": "agent_research",
            "confidence": 0.85,
            "result": {"summary": "Option A"},
        },
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 65,
            "agent_id": "agent_writer",
            "confidence": 0.60,
            "result": {"summary": "Option B"},
        },
    )
    final_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "completed",
            "progress": 100,
            "agent_id": "agent_planner",
            "confidence": 0.55,
            "result": {"summary": "Option B"},
        },
    )
    assert final_response.status_code == 200

    consensus_snapshot = client.get(f"/api/tasks/{task_id}/consensus")
    assert consensus_snapshot.status_code == 200
    consensus_json = consensus_snapshot.json()["consensus"]
    assert consensus_json["decided_by"] == "majority_vote"
    assert consensus_json["decision_result"]["summary"] == "Option B"
    assert consensus_json["explanation"]["comparison_basis"] == "majority count with confidence tie-break"


def test_env_default_strategy_applies_when_metadata_missing(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_CONSENSUS_STRATEGY_DEFAULT", "majority_vote")

    task_response = client.post(
        "/api/tasks",
        json={"objective": "choose release title", "priority": "high"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 35,
            "agent_id": "agent_research",
            "confidence": 0.92,
            "result": {"summary": "Title A"},
        },
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 70,
            "agent_id": "agent_writer",
            "confidence": 0.40,
            "result": {"summary": "Title B"},
        },
    )
    final_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "completed",
            "progress": 100,
            "agent_id": "agent_planner",
            "confidence": 0.30,
            "result": {"summary": "Title B"},
        },
    )
    assert final_response.status_code == 200

    consensus_snapshot = client.get(f"/api/tasks/{task_id}/consensus")
    assert consensus_snapshot.status_code == 200
    consensus_json = consensus_snapshot.json()["consensus"]
    assert consensus_json["decided_by"] == "majority_vote"
    assert consensus_json["decision_result"]["summary"] == "Title B"


def test_task_strategy_overrides_env_default(monkeypatch) -> None:
    monkeypatch.setenv("NEXUSAI_CONSENSUS_STRATEGY_DEFAULT", "majority_vote")

    task_response = client.post(
        "/api/tasks",
        json={
            "objective": "choose architecture baseline",
            "priority": "high",
            "metadata": {"consensus_strategy": "highest_confidence"},
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 40,
            "agent_id": "agent_research",
            "confidence": 0.95,
            "result": {"summary": "Baseline X"},
        },
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "completed",
            "progress": 100,
            "agent_id": "agent_writer",
            "confidence": 0.50,
            "result": {"summary": "Baseline Y"},
        },
    )

    consensus_snapshot = client.get(f"/api/tasks/{task_id}/consensus")
    assert consensus_snapshot.status_code == 200
    consensus_json = consensus_snapshot.json()["consensus"]
    assert consensus_json["decided_by"] == "highest_confidence"
    assert consensus_json["decision_result"]["summary"] == "Baseline X"


def test_invalid_strategy_falls_back_to_highest_confidence() -> None:
    task_response = client.post(
        "/api/tasks",
        json={
            "objective": "choose naming style",
            "priority": "medium",
            "metadata": {"consensus_strategy": "unknown_strategy"},
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 55,
            "agent_id": "agent_research",
            "confidence": 0.91,
            "result": {"summary": "Style One"},
        },
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "completed",
            "progress": 100,
            "agent_id": "agent_writer",
            "confidence": 0.52,
            "result": {"summary": "Style Two"},
        },
    )

    consensus_snapshot = client.get(f"/api/tasks/{task_id}/consensus")
    consensus_json = consensus_snapshot.json()["consensus"]
    assert consensus_json["decided_by"] == "highest_confidence"
    assert "Invalid task strategy" in consensus_json["reason"]


def test_task_events_history_contains_failed_once() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "simulate a failed flow", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    first_failed = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "failed",
            "progress": 88,
            "result": {"error": "upstream timeout"},
        },
    )
    assert first_failed.status_code == 200

    second_failed = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "failed",
            "progress": 90,
            "result": {"error": "still failing"},
        },
    )
    assert second_failed.status_code == 200

    events_response = client.get(f"/api/tasks/{task_id}/events")
    assert events_response.status_code == 200
    event_types = [event["type"] for event in events_response.json()]
    assert "TaskFailed" in event_types
    assert event_types.count("TaskFailed") == 1


def test_task_handoff_failed_task_returns_409() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "failed handoff guard", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    claim_response = client.post(
        f"/api/tasks/{task_id}/claim",
        json={"agent_id": "agent_planner"},
    )
    assert claim_response.status_code == 200

    failed_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "failed", "progress": 100, "result": {"error": "failed"}},
    )
    assert failed_response.status_code == 200

    handoff_response = client.post(
        f"/api/tasks/{task_id}/handoff",
        json={"from_agent_id": "agent_planner", "to_agent_id": "agent_writer", "reason": "should not happen"},
    )
    assert handoff_response.status_code == 409
    assert handoff_response.json()["detail"]["error_code"] == "E_TASK_TERMINAL_HANDOFF"


def test_task_events_unknown_task_returns_404() -> None:
    events_response = client.get("/api/tasks/task_missing/events")
    assert events_response.status_code == 404


def test_task_events_support_limit_and_type_filter() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "collect filtered events", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "in_progress",
            "progress": 50,
            "agent_id": "agent_research",
            "confidence": 0.6,
            "result": {"summary": "first"},
        },
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "failed",
            "progress": 90,
            "error_code": "E_TIMEOUT",
            "error_message": "worker timeout",
            "result": {"error": "worker timeout"},
        },
    )

    limited = client.get(f"/api/tasks/{task_id}/events?limit=2")
    assert limited.status_code == 200
    assert len(limited.json()) == 2
    assert limited.headers["x-total-count"]

    failed_only = client.get(f"/api/tasks/{task_id}/events?type=TaskFailed")
    assert failed_only.status_code == 200
    failed_events = failed_only.json()
    assert len(failed_events) == 1
    assert failed_events[0]["type"] == "TaskFailed"
    assert failed_events[0]["payload"]["error_code"] == "E_TIMEOUT"
    assert failed_events[0]["payload"]["error_message"] == "worker timeout"

    multi_type = client.get(
        f"/api/tasks/{task_id}/events?type=TaskFailed&type=TaskResult"
    )
    assert multi_type.status_code == 200
    multi_type_values = {event["type"] for event in multi_type.json()}
    assert multi_type_values == {"TaskFailed", "TaskResult"}

    paged = client.get(f"/api/tasks/{task_id}/events?offset=1&limit=2")
    assert paged.status_code == 200
    assert len(paged.json()) == 2

    out_of_range = client.get(f"/api/tasks/{task_id}/events?offset=999&limit=10")
    assert out_of_range.status_code == 200
    assert out_of_range.json() == []

    asc_events = client.get(f"/api/tasks/{task_id}/events?type=TaskFailed&type=TaskResult&sort=asc")
    desc_events = client.get(f"/api/tasks/{task_id}/events?type=TaskFailed&type=TaskResult&sort=desc")
    asc_types = [event["type"] for event in asc_events.json()]
    desc_types = [event["type"] for event in desc_events.json()]
    assert desc_types == list(reversed(asc_types))
    assert int(desc_events.headers["x-total-count"]) == len(desc_types)


def test_task_failed_error_message_falls_back_to_result_error() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "fallback error test", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    fail_response = client.patch(
        f"/api/tasks/{task_id}/status",
        json={
            "status": "failed",
            "progress": 100,
            "error_code": "E_AGENT",
            "result": {"error": "agent crashed"},
        },
    )
    assert fail_response.status_code == 200

    failed_only = client.get(f"/api/tasks/{task_id}/events?type=TaskFailed")
    failed_event = failed_only.json()[0]
    assert failed_event["payload"]["error_code"] == "E_AGENT"
    assert failed_event["payload"]["error_message"] == "agent crashed"


def test_task_events_support_time_range_filter() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "time range event filter", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "in_progress", "progress": 40, "result": {"summary": "step one"}},
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "step two"}},
    )

    all_events_resp = client.get(f"/api/tasks/{task_id}/events")
    assert all_events_resp.status_code == 200
    all_events = all_events_resp.json()
    assert len(all_events) >= 4

    # Pick a middle timestamp and ensure filtering returns a suffix of events.
    cutoff = all_events[-2]["timestamp"]
    filtered_resp = client.get(f"/api/tasks/{task_id}/events?from={quote(cutoff, safe='')}" )
    assert filtered_resp.status_code == 200
    filtered = filtered_resp.json()
    assert len(filtered) <= len(all_events)
    assert all(event["timestamp"] >= cutoff for event in filtered)


def test_task_events_invalid_time_range_returns_422() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "invalid range test", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    response = client.get(
        f"/api/tasks/{task_id}/events?from=2026-04-06T12:00:00Z&to=2026-04-05T12:00:00Z"
    )
    assert response.status_code == 422


def test_task_events_include_meta_wrapper() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "meta wrapper test", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "done"}},
    )

    events_response = client.get(
        f"/api/tasks/{task_id}/events?include_meta=true&limit=2&sort=desc"
    )
    assert events_response.status_code == 200
    body = events_response.json()
    assert isinstance(body, dict)
    assert body["sort"] == "desc"
    assert body["limit"] == 2
    assert "has_more" in body
    assert isinstance(body["items"], list)
    assert int(events_response.headers["x-total-count"]) == body["total_count"]


def test_task_events_cursor_pagination() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "cursor pagination test", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "in_progress", "progress": 50, "result": {"summary": "phase 1"}},
    )
    client.patch(
        f"/api/tasks/{task_id}/status",
        json={"status": "completed", "progress": 100, "result": {"summary": "phase 2"}},
    )

    first_page = client.get(
        f"/api/tasks/{task_id}/events?include_meta=true&limit=2&sort=asc"
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["has_more"] is True
    assert first_body["next_cursor"] is not None
    assert len(first_body["items"]) == 2

    second_page = client.get(
        f"/api/tasks/{task_id}/events?include_meta=true&limit=2&cursor={first_body['next_cursor']}&offset=0"
    )
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert second_body["offset"] == int(first_body["next_cursor"])
    assert len(second_body["items"]) >= 1


def test_task_events_invalid_cursor_returns_422() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "invalid cursor test", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    invalid_response = client.get(f"/api/tasks/{task_id}/events?cursor=abc")
    assert invalid_response.status_code == 422


def test_execute_task_real_path_success() -> None:
    class FakeExecutionService:
        def execute(self, **_: object):
            class Result:
                confidence = 0.91
                result = {
                    "summary": "real execution output",
                    "mode": "real",
                    "provider": "test-provider",
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "execute with real agent path", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={"agent_id": "agent_planner"},
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["mode"] == "real"
        assert body["result"]["summary"] == "real execution output"
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_forwards_request_api_key_to_execution_service() -> None:
    captured_api_keys: list[str | None] = []

    class FakeExecutionService:
        def execute(self, **kwargs: object):
            captured_api_keys.append(kwargs.get("api_key") if isinstance(kwargs, dict) else None)

            class Result:
                confidence = 0.91
                result = {
                    "summary": "real execution output with request key",
                    "mode": "real",
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "execute with forwarded api key", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={"agent_id": "agent_planner", "api_key": "user-supplied-token"},
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["mode"] == "real"
        assert body["result"]["summary"] == "real execution output with request key"
        assert captured_api_keys == ["user-supplied-token"]
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_fallback_to_simulate_when_provider_fails() -> None:
    class FailingExecutionService:
        def execute(self, **_: object):
            raise AgentExecutionError("E_EXECUTION_PROVIDER", "provider unavailable")

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FailingExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "fallback execution", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "agent_id": "agent_planner",
                "allow_fallback": True,
                "fallback_mode": "simulate",
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["mode"] == "fallback_simulated"
        assert body["result"]["fallback_code"] == "E_EXECUTION_PROVIDER"
        assert body["result"]["fallback_error"]["error_category"] == "provider"
        assert body["result"]["fallback_error"]["retryable"] is True
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_fail_when_fallback_disabled() -> None:
    class FailingExecutionService:
        def execute(self, **_: object):
            raise AgentExecutionError("E_EXECUTION_PROVIDER", "provider unavailable")

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FailingExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "strict execution failure", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "agent_id": "agent_planner",
                "allow_fallback": False,
                "fallback_mode": "fail",
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "failed"
        assert body["attempt_history"][-1]["error_code"] == "E_EXECUTION_PROVIDER"
        assert body["result"]["error_details"]["error_category"] == "provider"
        assert body["result"]["error_details"]["retryable"] is True
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_parallel_all_fail_returns_structured_failure() -> None:
    class FailingExecutionService:
        def execute(self, **_: object):
            raise AgentExecutionError("E_EXECUTION_PROVIDER", "parallel provider unavailable")

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FailingExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "parallel all fail", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "execution_mode": "parallel",
                "pipeline_agent_ids": ["agent_research", "agent_writer"],
                "allow_fallback": False,
                "fallback_mode": "fail",
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "failed"
        assert body["result"]["error_details"]["error_code"] == "E_EXECUTION_PROVIDER"
        assert body["result"]["error_details"]["error_category"] == "provider"
        assert body["result"]["error_details"]["retryable"] is True

        failed_events = client.get(f"/api/tasks/{task_id}/events?type=TaskFailed")
        assert failed_events.status_code == 200
        failed_payload = failed_events.json()[0]["payload"]
        assert failed_payload["error_code"] == "E_EXECUTION_PROVIDER"
        assert failed_payload["error_category"] == "provider"
        assert failed_payload["retryable"] is True
        assert isinstance(failed_payload["user_message"], str)
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_result_contains_execution_metrics() -> None:
    class FakeExecutionService:
        def execute(self, **_: object):
            class Result:
                confidence = 0.88
                result = {
                    "summary": "metrics result",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 12, "usage": {"total_tokens": 42}},
                }
                metrics = {"latency_ms": 12, "usage": {"total_tokens": 42}}

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "execution metrics test", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={"agent_id": "agent_planner"},
        )
        assert execute_response.status_code == 200
        result = execute_response.json()["result"]
        assert result["execution_metrics"]["latency_ms"] == 12
        assert result["execution_metrics"]["arbitration_mode"] == "off"
        assert result["execution_metrics"]["judge_triggered"] is False
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_passes_request_api_key_to_execution_service() -> None:
    class FakeExecutionService:
        received_api_keys: list[str | None] = []

        def execute(self, **kwargs: object):
            FakeExecutionService.received_api_keys.append(kwargs.get("api_key") if isinstance(kwargs, dict) else None)

            class Result:
                confidence = 0.9
                result = {
                    "summary": "api key forwarding result",
                    "mode": "real",
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "execute with request api key", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={"agent_id": "agent_planner", "api_key": "user-supplied-token"},
        )
        assert execute_response.status_code == 200
        assert FakeExecutionService.received_api_keys
        assert FakeExecutionService.received_api_keys[0] == "user-supplied-token"
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_judge_arbitration_on_conflict() -> None:
    class FakeExecutionService:
        def execute(self, **kwargs: object):
            agent = kwargs["agent"]
            system_instruction = kwargs.get("system_instruction")

            class Result:
                confidence = 0.79
                metrics = {"latency_ms": 9, "usage": {"total_tokens": 55}}
                result = {
                    "summary": "primary summary from planner",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 9, "usage": {"total_tokens": 55}},
                }

            if agent.role == "reviewer" and isinstance(system_instruction, str) and "judge agent" in system_instruction:
                Result.result = {
                    "summary": "judge final summary",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 5, "usage": {"total_tokens": 20}},
                }
                Result.metrics = {"latency_ms": 5, "usage": {"total_tokens": 20}}

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "judge arbitration test", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        conflict_seed_response = client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "in_progress",
                "progress": 30,
                "agent_id": "agent_writer",
                "result": {"summary": "different previous proposal"},
                "confidence": 0.6,
            },
        )
        assert conflict_seed_response.status_code == 200

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "agent_id": "agent_planner",
                "arbitration_mode": "judge_on_conflict",
                "judge_agent_id": "agent_reviewer",
            },
        )
        assert execute_response.status_code == 200
        result = execute_response.json()["result"]
        assert result["summary"] == "judge final summary"
        assert result["arbitration"]["decision"] == "judge_override"
        assert result["arbitration"]["judge_agent_id"] == "agent_reviewer"
        assert result["execution_metrics"]["judge_triggered"] is True
        assert result["arbitration"]["explanation"]["selection_basis"] == "judge override applied"
        explanation = result["arbitration"]["explanation"]
        assert {"conflict_detected", "primary_summary", "judge_summary", "selected_summary", "selection_basis"}.issubset(explanation.keys())
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


@pytest.mark.parametrize("sample", json.loads(_CONFLICT_SAMPLE_FIXTURE.read_text(encoding="utf-8")))
def test_consensus_conflict_samples_api_e2e(sample: dict[str, object]) -> None:
    strategy = str(sample["strategy"])
    expected = sample["expected"]
    proposals = sample["proposals"]

    task_response = client.post(
        "/api/tasks",
        json={
            "objective": f"api consensus sample {sample['name']}",
            "priority": "medium",
            "metadata": {"consensus_strategy": strategy},
        },
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    for index, proposal in enumerate(proposals, start=1):
        status_response = client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "in_progress",
                "progress": min(10 * index, 90),
                "agent_id": proposal["agent_id"],
                "result": {"summary": proposal["summary"]},
                "confidence": proposal["confidence"],
            },
        )
        assert status_response.status_code == 200

    consensus_response = client.get(f"/api/tasks/{task_id}/consensus")
    assert consensus_response.status_code == 200
    consensus = consensus_response.json()["consensus"]
    assert consensus is not None
    assert consensus["decided_by"] == expected["decided_by"]
    assert consensus["conflict_detected"] is expected["conflict_detected"]
    explanation = consensus["explanation"]
    assert explanation["selected_agent_id"] == expected["selected_agent_id"]
    assert isinstance(explanation["views"], list)

    event_response = client.get(f"/api/tasks/{task_id}/events?type=Decision")
    assert event_response.status_code == 200
    decision_events = event_response.json()
    assert decision_events
    latest_decision = decision_events[-1]
    assert latest_decision["payload"]["decided_by"] == expected["decided_by"]
    assert latest_decision["payload"]["explanation"]["selected_agent_id"] == expected["selected_agent_id"]


def test_execute_task_judge_arbitration_handles_missing_judge_agent() -> None:
    class FakeExecutionService:
        def execute(self, **_: object):
            class Result:
                confidence = 0.8
                metrics = {"latency_ms": 8, "usage": {"total_tokens": 21}}
                result = {
                    "summary": "primary summary",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 8, "usage": {"total_tokens": 21}},
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "judge missing path", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        client.patch(
            f"/api/tasks/{task_id}/status",
            json={
                "status": "in_progress",
                "progress": 20,
                "agent_id": "agent_writer",
                "result": {"summary": "different summary"},
                "confidence": 0.4,
            },
        )

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "agent_id": "agent_planner",
                "arbitration_mode": "judge_on_conflict",
                "judge_agent_id": "agent_missing",
            },
        )
        assert execute_response.status_code == 200
        result = execute_response.json()["result"]
        assert result["summary"] == "primary summary"
        assert result["arbitration"]["decision"] == "judge_unavailable"
        assert result["execution_metrics"]["judge_triggered"] is False
        assert result["arbitration"]["explanation"]["selection_basis"] == "judge unavailable; kept primary summary"
        explanation = result["arbitration"]["explanation"]
        assert {"conflict_detected", "selected_summary", "selection_basis"}.issubset(explanation.keys())
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_pipeline_mode_runs_multiple_agents_in_order() -> None:
    class FakeExecutionService:
        def execute(self, **kwargs: object):
            agent = kwargs["agent"]

            class Result:
                confidence = 0.85
                metrics = {"latency_ms": 7, "usage": {"total_tokens": 30}}
                result = {
                    "summary": f"summary from {agent.agent_id}",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 7, "usage": {"total_tokens": 30}},
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "pipeline execution test", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "execution_mode": "pipeline",
                "pipeline_agent_ids": ["agent_planner", "agent_research", "agent_writer"],
                "arbitration_mode": "off",
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["summary"] == "summary from agent_writer"
        assert body["result"]["execution_metrics"]["execution_mode"] == "pipeline"
        assert body["result"]["execution_metrics"]["pipeline_steps"] == 3
        assert len(body["result"]["pipeline"]["steps"]) == 3
        assert body["current_agent_id"] == "agent_writer"

        events_response = client.get(f"/api/tasks/{task_id}/events")
        assert events_response.status_code == 200
        event_types = [event["type"] for event in events_response.json()]
        assert "TaskPipelineStart" in event_types
        assert event_types.count("AgentExecutionStart") == 3
        assert event_types.count("AgentExecutionResult") == 3
        assert "TaskPipelineFinish" in event_types
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_pipeline_mode_can_fallback_on_agent_error() -> None:
    class FakeExecutionService:
        def __init__(self) -> None:
            self._calls = 0

        def execute(self, **kwargs: object):
            self._calls += 1
            if self._calls == 2:
                raise AgentExecutionError("E_EXECUTION_PROVIDER", "step provider unavailable")

            agent = kwargs["agent"]

            class Result:
                confidence = 0.8
                metrics = {"latency_ms": 5, "usage": {"total_tokens": 12}}
                result = {
                    "summary": f"ok from {agent.agent_id}",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 5, "usage": {"total_tokens": 12}},
                }

            return Result()

    fake_service = FakeExecutionService()
    app.dependency_overrides[tasks_api.get_execution_service] = lambda: fake_service
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "pipeline fallback test", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "execution_mode": "pipeline",
                "pipeline_agent_ids": ["agent_planner", "agent_research"],
                "allow_fallback": True,
                "fallback_mode": "simulate",
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["mode"] == "fallback_simulated"
        assert body["result"]["execution_metrics"]["execution_mode"] == "pipeline"
        assert body["result"]["execution_metrics"]["pipeline_steps"] == 2

        events_response = client.get(f"/api/tasks/{task_id}/events?type=AgentExecutionError")
        assert events_response.status_code == 200
        error_events = events_response.json()
        assert len(error_events) == 1
        assert error_events[0]["payload"]["error_code"] == "E_EXECUTION_PROVIDER"
        assert error_events[0]["payload"]["error_category"] == "provider"
        assert error_events[0]["payload"]["retryable"] is True
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_preview_returns_ordered_plan_without_side_effects() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "preview pipeline plan", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    preview_response = client.post(
        f"/api/tasks/{task_id}/execute/preview",
        json={
            "execution_mode": "pipeline",
            "pipeline_agent_ids": ["agent_planner", "agent_research", "agent_writer"],
            "pipeline_error_policy": "continue",
            "arbitration_mode": "judge_on_conflict",
        },
    )
    assert preview_response.status_code == 200
    body = preview_response.json()
    assert body["task_id"] == task_id
    assert body["execution_mode"] == "pipeline"
    assert body["pipeline_error_policy"] == "continue"
    assert len(body["steps"]) == 3
    assert body["steps"][0]["transition_action"] in {"claim", "keep"}
    assert body["steps"][1]["transition_action"] == "handoff"
    event_types = [event["event_type"] for event in body["estimated_events"]]
    assert "TaskPipelineStart" in event_types
    assert event_types.count("AgentExecutionStart") == 3
    assert event_types.count("AgentExecutionResult") == 3
    assert "TaskPipelineFinish" in event_types
    assert "TaskFailed" in event_types
    first_agent_start = next(event for event in body["estimated_events"] if event["event_type"] == "AgentExecutionStart")
    assert first_agent_start["step"] == 1
    assert first_agent_start["agent_id"] == "agent_planner"

    warning_codes = {item["code"] for item in body["preview_warnings"]}
    assert "W_PREVIEW_PARTIAL_PIPELINE" in warning_codes

    task_snapshot = client.get(f"/api/tasks/{task_id}")
    assert task_snapshot.status_code == 200
    assert task_snapshot.json()["status"] == "in_progress"


def test_execute_task_preview_single_mode_estimated_events_are_compact() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "preview single plan", "priority": "low"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    preview_response = client.post(
        f"/api/tasks/{task_id}/execute/preview",
        json={
            "execution_mode": "single",
            "agent_id": "agent_planner",
            "allow_fallback": False,
            "fallback_mode": "fail",
        },
    )
    assert preview_response.status_code == 200
    body = preview_response.json()
    assert body["execution_mode"] == "single"
    assert len(body["steps"]) == 1

    event_types = [event["event_type"] for event in body["estimated_events"]]
    assert "TaskPipelineStart" not in event_types
    assert "TaskPipelineFinish" not in event_types
    assert event_types.count("AgentExecutionStart") == 1
    assert event_types.count("AgentExecutionResult") == 1

    warning_codes = {item["code"] for item in body["preview_warnings"]}
    assert "W_PREVIEW_STRICT_FAILURE_PATH" in warning_codes
    strict_warning = next(item for item in body["preview_warnings"] if item["code"] == "W_PREVIEW_STRICT_FAILURE_PATH")
    assert strict_warning["applies_to_step"] is None


def test_execute_task_preview_warns_when_judge_is_missing() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "preview missing judge", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    preview_response = client.post(
        f"/api/tasks/{task_id}/execute/preview",
        json={
            "execution_mode": "single",
            "agent_id": "agent_planner",
            "arbitration_mode": "judge_always",
            "judge_agent_id": "agent_not_found",
        },
    )
    assert preview_response.status_code == 200
    body = preview_response.json()

    warning_codes = {item["code"] for item in body["preview_warnings"]}
    assert "W_PREVIEW_JUDGE_MISSING" in warning_codes
    judge_warning = next(item for item in body["preview_warnings"] if item["code"] == "W_PREVIEW_JUDGE_MISSING")
    assert judge_warning["applies_to_step"] is None


def test_execute_task_preview_marks_single_pipeline_step_warning_with_step_number() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "single-step pipeline preview", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    preview_response = client.post(
        f"/api/tasks/{task_id}/execute/preview",
        json={
            "execution_mode": "pipeline",
            "pipeline_agent_ids": ["agent_planner"],
        },
    )
    assert preview_response.status_code == 200
    body = preview_response.json()

    pipeline_warning = next(item for item in body["preview_warnings"] if item["code"] == "W_PREVIEW_PIPELINE_SINGLE_STEP")
    assert pipeline_warning["applies_to_step"] == 1


def test_execute_task_preview_parallel_mode_returns_dispatch_plan() -> None:
    task_response = client.post(
        "/api/tasks",
        json={"objective": "parallel preview plan", "priority": "medium"},
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["task_id"]

    preview_response = client.post(
        f"/api/tasks/{task_id}/execute/preview",
        json={
            "execution_mode": "parallel",
            "pipeline_agent_ids": ["agent_research", "agent_writer", "agent_analyst"],
            "pipeline_error_policy": "continue",
        },
    )
    assert preview_response.status_code == 200
    body = preview_response.json()
    assert body["execution_mode"] == "parallel"
    assert all(step["transition_action"] == "parallel_dispatch" for step in body["steps"])
    warning_codes = {item["code"] for item in body["preview_warnings"]}
    assert "W_PREVIEW_PARTIAL_PARALLEL" in warning_codes


def test_execute_task_pipeline_continue_policy_keeps_running_after_step_error() -> None:
    class FakeExecutionService:
        def execute(self, **kwargs: object):
            agent = kwargs["agent"]
            if agent.agent_id == "agent_research":
                raise AgentExecutionError("E_EXECUTION_PROVIDER", "research provider error")

            class Result:
                confidence = 0.83
                metrics = {"latency_ms": 6, "usage": {"total_tokens": 14}}
                result = {
                    "summary": f"ok from {agent.agent_id}",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 6, "usage": {"total_tokens": 14}},
                }

            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "pipeline continue policy", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "execution_mode": "pipeline",
                "pipeline_agent_ids": ["agent_planner", "agent_research", "agent_writer"],
                "pipeline_error_policy": "continue",
                "allow_fallback": False,
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["summary"] == "ok from agent_writer"
        assert body["result"]["execution_metrics"]["pipeline_error_policy"] == "continue"
        assert body["result"]["execution_metrics"]["pipeline_error_count"] == 1
        assert len(body["result"]["pipeline"]["steps"]) == 2
        assert len(body["result"]["pipeline"]["errors"]) == 1

        error_events = client.get(f"/api/tasks/{task_id}/events?type=AgentExecutionError")
        assert error_events.status_code == 200
        assert len(error_events.json()) == 1
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_parallel_mode_selects_highest_confidence_result() -> None:
    class FakeExecutionService:
        def execute(self, **kwargs: object):
            agent = kwargs["agent"]

            class Result:
                confidence = 0.5
                metrics = {"latency_ms": 4, "usage": {"total_tokens": 10}}
                result = {
                    "summary": f"parallel summary from {agent.agent_id}",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 4, "usage": {"total_tokens": 10}},
                }

            if agent.agent_id == "agent_writer":
                Result.confidence = 0.9
            elif agent.agent_id == "agent_analyst":
                Result.confidence = 0.7
            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "parallel execution winner", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "execution_mode": "parallel",
                "pipeline_agent_ids": ["agent_research", "agent_writer", "agent_analyst"],
                "allow_fallback": False,
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["summary"] == "parallel summary from agent_writer"
        assert body["result"]["parallel"]["selection"] == "highest_confidence"
        assert len(body["result"]["parallel"]["steps"]) == 3
        assert body["result"]["execution_metrics"]["execution_mode"] == "parallel"
        assert body["result"]["execution_metrics"]["parallel_steps"] == 3
        assert body["result"]["execution_metrics"]["selected_agent_id"] == "agent_writer"

        claim_events = client.get(f"/api/tasks/{task_id}/events?type=TaskClaim&sort=desc")
        assert claim_events.status_code == 200
        assert claim_events.json()[0]["payload"]["agent_id"] == "agent_writer"
        assert claim_events.json()[0]["payload"]["note"] == "selected as parallel winner"
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


def test_execute_task_parallel_mode_continue_policy_keeps_partial_successes() -> None:
    class FakeExecutionService:
        def execute(self, **kwargs: object):
            agent = kwargs["agent"]
            if agent.agent_id == "agent_writer":
                raise AgentExecutionError("E_EXECUTION_PROVIDER", "writer failed")

            class Result:
                confidence = 0.65
                metrics = {"latency_ms": 5, "usage": {"total_tokens": 11}}
                result = {
                    "summary": f"parallel ok from {agent.agent_id}",
                    "mode": "real",
                    "execution_metrics": {"latency_ms": 5, "usage": {"total_tokens": 11}},
                }

            if agent.agent_id == "agent_analyst":
                Result.confidence = 0.8
            return Result()

    app.dependency_overrides[tasks_api.get_execution_service] = lambda: FakeExecutionService()
    try:
        task_response = client.post(
            "/api/tasks",
            json={"objective": "parallel partial success", "priority": "medium"},
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["task_id"]

        execute_response = client.post(
            f"/api/tasks/{task_id}/execute",
            json={
                "execution_mode": "parallel",
                "pipeline_agent_ids": ["agent_research", "agent_writer", "agent_analyst"],
                "pipeline_error_policy": "continue",
                "allow_fallback": False,
            },
        )
        assert execute_response.status_code == 200
        body = execute_response.json()
        assert body["status"] == "completed"
        assert body["result"]["summary"] == "parallel ok from agent_analyst"
        assert len(body["result"]["parallel"]["steps"]) == 2
        assert len(body["result"]["parallel"]["errors"]) == 1
        assert body["result"]["execution_metrics"]["pipeline_error_count"] == 1
    finally:
        app.dependency_overrides.pop(tasks_api.get_execution_service, None)


