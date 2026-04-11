from pathlib import Path
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import TypedDict

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.main import app
from backend.app.api import auth as auth_api
from backend.app.api import tasks as tasks_api
from backend.app.services.message_bus import InMemoryMessageBus
from backend.app.services.store import InMemoryStore
from backend.app.services.auth_service import reset_auth_service


client = TestClient(app)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "change-me-admin-password"


class UserAuthContext(TypedDict):
    headers: dict[str, str]
    user_id: str


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


def _create_user_and_headers(admin_headers: dict[str, str], username: str, password: str = "password123") -> UserAuthContext:
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


def test_bootstrap_admin_can_login(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    reset_auth_service()

    response = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == ADMIN_USERNAME
    assert payload["user"]["role"] == "admin"
    assert isinstance(payload["access_token"], str) and payload["access_token"]
    assert payload["token_type"] == "bearer"


def test_register_requires_invite_code(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_AUTH_FILE", str(tmp_path / "auth.json"))
    reset_auth_service()

    response = client.post(
        "/api/auth/register",
        json={"username": "user-a", "password": "password123", "invite_code": "BADCODE"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "E_AUTH_INVITE_INVALID"


def test_admin_can_create_invite_and_register_user(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    reset_auth_service()

    login = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    admin_token = login.json()["access_token"]

    invite_response = client.post(
        "/api/auth/invites",
        json={"code": "NEXUS-TEST-001", "max_uses": 1, "expires_hours": 24},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_response.status_code == 200
    assert invite_response.json()["code"] == "NEXUS-TEST-001"

    register = client.post(
        "/api/auth/register",
        json={"username": "new-user", "password": "password123", "invite_code": "NEXUS-TEST-001"},
    )
    assert register.status_code == 200
    register_payload = register.json()
    assert register_payload["user"]["username"] == "new-user"
    assert register_payload["user"]["role"] == "viewer"
    assert register_payload["token_type"] == "bearer"


def test_admin_user_management_and_invite_revoke(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_AUTH_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    reset_auth_service()

    login = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    admin_token = login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    invite_response = client.post(
        "/api/auth/invites",
        json={"code": "NEXUS-TEST-ADMIN", "max_uses": 2, "expires_hours": 24},
        headers=admin_headers,
    )
    assert invite_response.status_code == 200

    register = client.post(
        "/api/auth/register",
        json={"username": "managed-user", "password": "password123", "invite_code": "NEXUS-TEST-ADMIN"},
    )
    assert register.status_code == 200

    users_response = client.get("/api/auth/users", headers=admin_headers)
    assert users_response.status_code == 200
    usernames = {item["username"] for item in users_response.json()}
    assert ADMIN_USERNAME in usernames
    assert "managed-user" in usernames

    disable_response = client.patch(
        "/api/auth/users/managed-user/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["is_active"] is False

    blocked_login = client.post(
        "/api/auth/login",
        json={"username": "managed-user", "password": "password123"},
    )
    assert blocked_login.status_code == 401

    enable_response = client.patch(
        "/api/auth/users/managed-user/status",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert enable_response.status_code == 200
    assert enable_response.json()["is_active"] is True

    reset_response = client.post(
        "/api/auth/users/managed-user/reset-password",
        json={"new_password": "newpassword456"},
        headers=admin_headers,
    )
    assert reset_response.status_code == 200

    login_after_reset = client.post(
        "/api/auth/login",
        json={"username": "managed-user", "password": "newpassword456"},
    )
    assert login_after_reset.status_code == 200

    revoke_response = client.delete("/api/auth/invites/NEXUS-TEST-ADMIN", headers=admin_headers)
    assert revoke_response.status_code == 200

    invite_reuse = client.post(
        "/api/auth/register",
        json={"username": "another-user", "password": "password123", "invite_code": "NEXUS-TEST-ADMIN"},
    )
    assert invite_reuse.status_code == 400


def test_task_data_isolation_and_per_task_delete(monkeypatch, tmp_path: Path) -> None:
    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[tasks_api.get_message_bus] = lambda: bus
    try:
        user_a = _create_user_and_headers(admin_headers, "user-a")
        user_b = _create_user_and_headers(admin_headers, "user-b")
        headers_a = user_a["headers"]
        headers_b = user_b["headers"]

        create_response = client.post(
            "/api/tasks",
            json={"objective": "owned by user a", "priority": "medium"},
            headers=headers_a,
        )
        assert create_response.status_code == 201
        task = create_response.json()
        task_id = task["task_id"]
        assert task["owner_user_id"] == user_a["user_id"]
        assert task["owner_username"] == "user-a"

        list_a = client.get("/api/tasks", headers=headers_a)
        assert list_a.status_code == 200
        assert any(item["task_id"] == task_id for item in list_a.json())

        list_b = client.get("/api/tasks", headers=headers_b)
        assert list_b.status_code == 200
        assert all(item["task_id"] != task_id for item in list_b.json())

        get_b = client.get(f"/api/tasks/{task_id}", headers=headers_b)
        assert get_b.status_code == 404

        delete_b = client.delete(f"/api/tasks/{task_id}", headers=headers_b)
        assert delete_b.status_code == 404

        delete_a = client.delete(f"/api/tasks/{task_id}", headers=headers_a)
        assert delete_a.status_code == 200
        assert delete_a.json()["status"] == "deleted"

        get_after_delete = client.get(f"/api/tasks/{task_id}", headers=headers_a)
        assert get_after_delete.status_code == 404
    finally:
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(tasks_api.get_message_bus, None)


def test_delete_my_tasks_only_removes_current_user_tasks(monkeypatch, tmp_path: Path) -> None:
    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[tasks_api.get_message_bus] = lambda: bus
    try:
        user_a = _create_user_and_headers(admin_headers, "user-a")
        user_b = _create_user_and_headers(admin_headers, "user-b")
        headers_a = user_a["headers"]
        headers_b = user_b["headers"]

        for idx in range(2):
            response = client.post(
                "/api/tasks",
                json={"objective": f"a-task-{idx}", "priority": "low"},
                headers=headers_a,
            )
            assert response.status_code == 201

        response_b = client.post(
            "/api/tasks",
            json={"objective": "b-task", "priority": "low"},
            headers=headers_b,
        )
        assert response_b.status_code == 201

        delete_me = client.delete("/api/tasks/me", headers=headers_a)
        assert delete_me.status_code == 200
        assert delete_me.json()["deleted_count"] == 2

        list_a = client.get("/api/tasks", headers=headers_a)
        assert list_a.status_code == 200
        assert list_a.json() == []

        list_b = client.get("/api/tasks", headers=headers_b)
        assert list_b.status_code == 200
        assert len(list_b.json()) == 1
        assert list_b.json()[0]["owner_user_id"] == user_b["user_id"]
    finally:
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(tasks_api.get_message_bus, None)


def test_api_key_only_cannot_bypass_task_visibility(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key,admin-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "viewer-key:viewer,admin-key:admin")

    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[tasks_api.get_message_bus] = lambda: bus
    try:
        user = _create_user_and_headers(admin_headers, "api-key-visible-user")
        user_headers = user["headers"]

        create_response = client.post(
            "/api/tasks",
            json={"objective": "bearer-owned task", "priority": "medium"},
            headers=user_headers,
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]

        viewer_headers = {"X-API-Key": "viewer-key"}

        list_response = client.get("/api/tasks", headers=viewer_headers)
        assert list_response.status_code == 200
        assert list_response.json() == []

        get_response = client.get(f"/api/tasks/{task_id}", headers=viewer_headers)
        assert get_response.status_code == 404

        delete_response = client.delete(f"/api/tasks/{task_id}", headers=viewer_headers)
        assert delete_response.status_code == 404

        admin_task_list = client.get("/api/tasks", headers={"X-API-Key": "admin-key"})
        assert admin_task_list.status_code == 200
        assert all(task["task_id"] != task_id for task in admin_task_list.json())

        admin_get = client.get(f"/api/tasks/{task_id}", headers={"X-API-Key": "admin-key"})
        assert admin_get.status_code == 404
    finally:
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(tasks_api.get_message_bus, None)


def test_bearer_user_context_wins_when_api_key_is_also_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NEXUSAI_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUSAI_API_KEYS", "viewer-key")
    monkeypatch.setenv("NEXUSAI_API_KEY_ROLES", "viewer-key:viewer")

    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[tasks_api.get_message_bus] = lambda: bus
    try:
        user = _create_user_and_headers(admin_headers, "mixed-auth-user")
        mixed_headers = dict(user["headers"])
        mixed_headers["X-API-Key"] = "viewer-key"

        create_response = client.post(
            "/api/tasks",
            json={"objective": "owned despite extra api key", "priority": "medium"},
            headers=mixed_headers,
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["owner_user_id"] == user["user_id"]
        assert created["owner_username"] == "mixed-auth-user"

        list_response = client.get("/api/tasks", headers=mixed_headers)
        assert list_response.status_code == 200
        task_ids = {item["task_id"] for item in list_response.json()}
        assert created["task_id"] in task_ids
    finally:
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(tasks_api.get_message_bus, None)


def test_exhausted_invite_is_auto_invalidated_and_hidden(monkeypatch, tmp_path: Path) -> None:
    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)

    create_invite_response = client.post(
        "/api/auth/invites",
        json={"code": "AUTO-HIDE-ONCE", "max_uses": 1, "expires_hours": 24},
        headers=admin_headers,
    )
    assert create_invite_response.status_code == 200

    register_response = client.post(
        "/api/auth/register",
        json={"username": "invite-once-user", "password": "password123", "invite_code": "AUTO-HIDE-ONCE"},
    )
    assert register_response.status_code == 200

    invites_response = client.get("/api/auth/invites", headers=admin_headers)
    assert invites_response.status_code == 200
    invite_codes = {item["code"] for item in invites_response.json()}
    assert "AUTO-HIDE-ONCE" not in invite_codes


def test_expired_invite_is_auto_invalidated_and_hidden(monkeypatch, tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    monkeypatch.setenv("NEXUSAI_AUTH_FILE", str(auth_file))
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setenv("NEXUSAI_AUTH_BOOTSTRAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    reset_auth_service()

    login = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create_invite_response = client.post(
        "/api/auth/invites",
        json={"code": "AUTO-EXPIRE", "max_uses": 2, "expires_hours": 24},
        headers=admin_headers,
    )
    assert create_invite_response.status_code == 200

    payload = json.loads(auth_file.read_text(encoding="utf-8"))
    payload["invites"]["AUTO-EXPIRE"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    auth_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    reset_auth_service()

    relogin = client.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert relogin.status_code == 200
    relogin_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}

    invites_response = client.get("/api/auth/invites", headers=relogin_headers)
    assert invites_response.status_code == 200
    invite_codes = {item["code"] for item in invites_response.json()}
    assert "AUTO-EXPIRE" not in invite_codes


def test_non_admin_can_delete_own_account_and_owned_tasks(monkeypatch, tmp_path: Path) -> None:
    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)
    store = InMemoryStore(persistence_enabled=False)
    bus = InMemoryMessageBus(persistence_enabled=False)
    app.dependency_overrides[tasks_api.get_store] = lambda: store
    app.dependency_overrides[tasks_api.get_message_bus] = lambda: bus
    app.dependency_overrides[auth_api.get_store] = lambda: store
    app.dependency_overrides[auth_api.get_message_bus] = lambda: bus
    try:
        user = _create_user_and_headers(admin_headers, "self-delete-user")
        user_headers = user["headers"]

        create_task_response = client.post(
            "/api/tasks",
            json={"objective": "task owned by deleting user", "priority": "low"},
            headers=user_headers,
        )
        assert create_task_response.status_code == 201

        delete_response = client.delete("/api/auth/me", headers=user_headers)
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"
        assert delete_response.json()["deleted_tasks"] == 1

        relogin_response = client.post(
            "/api/auth/login",
            json={"username": "self-delete-user", "password": "password123"},
        )
        assert relogin_response.status_code == 401

        admin_task_list = client.get("/api/tasks", headers=admin_headers)
        assert admin_task_list.status_code == 200
        assert all(task.get("owner_username") != "self-delete-user" for task in admin_task_list.json())
    finally:
        app.dependency_overrides.pop(tasks_api.get_store, None)
        app.dependency_overrides.pop(tasks_api.get_message_bus, None)
        app.dependency_overrides.pop(auth_api.get_store, None)
        app.dependency_overrides.pop(auth_api.get_message_bus, None)


def test_admin_cannot_delete_own_account(monkeypatch, tmp_path: Path) -> None:
    admin_headers = _bootstrap_admin_and_headers(monkeypatch, tmp_path)
    response = client.delete("/api/auth/me", headers=admin_headers)
    assert response.status_code == 403
    assert response.json()["detail"]["error_code"] == "E_AUTH_SELF_DELETE_ADMIN_FORBIDDEN"


