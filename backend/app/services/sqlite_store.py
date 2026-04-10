from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from ..agents import build_default_agents
from ..core.config import get_seed_file, get_sqlite_path, is_seed_apply_if_empty, is_seed_enabled
from ..models.agent import Agent, AgentRegister, AgentStatus
from ..models.task import (
    Task,
    TaskAttemptRecord,
    TaskConsensus,
    TaskCreate,
    TaskHandoffRecord,
    TaskProposal,
    TaskResultResponse,
    TaskStatus,
    TaskStatusUpdate,
)
from .json_persistence import load_json_file
from .store_contract import StoreContract


class SQLiteStore(StoreContract):
    """SQLite-backed store using JSON payload blobs for fast baseline persistence."""

    def __init__(self, *, sqlite_path: Path | None = None) -> None:
        self._lock = Lock()
        self._sqlite_path = sqlite_path or get_sqlite_path()
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._seed_file = get_seed_file()
        self._seed_enabled = is_seed_enabled()
        self._seed_apply_if_empty = is_seed_apply_if_empty()
        self._connection = sqlite3.connect(str(self._sqlite_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._ensure_schema()
        self._bootstrap_default_agents()
        self._apply_seed_data()

    def _ensure_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _serialize_model_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False)

    def _upsert_agent(self, agent: Agent) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO agents (agent_id, payload_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    created_at=excluded.created_at
                """,
                (
                    agent.agent_id,
                    self._serialize_model_payload(agent.model_dump(mode="json")),
                    agent.created_at.isoformat(),
                ),
            )

    def _upsert_task(self, task: Task) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO tasks (task_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    task.task_id,
                    self._serialize_model_payload(task.model_dump(mode="json")),
                    task.updated_at.isoformat(),
                ),
            )

    def _delete_all_tasks(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM tasks")

    def _delete_all_agents(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM agents")

    def _load_agent(self, agent_id: str) -> Agent | None:
        row = self._connection.execute(
            "SELECT payload_json FROM agents WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        return Agent.model_validate(json.loads(str(row["payload_json"])))

    def _load_task(self, task_id: str) -> Task | None:
        row = self._connection.execute(
            "SELECT payload_json FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        return Task.model_validate(json.loads(str(row["payload_json"])))

    def _load_all_agents(self) -> list[Agent]:
        rows = self._connection.execute("SELECT payload_json FROM agents ORDER BY created_at ASC").fetchall()
        return [Agent.model_validate(json.loads(str(row["payload_json"]))) for row in rows]

    def _load_all_tasks(self) -> list[Task]:
        rows = self._connection.execute("SELECT payload_json FROM tasks ORDER BY updated_at DESC").fetchall()
        return [Task.model_validate(json.loads(str(row["payload_json"]))) for row in rows]

    def _has_any_tasks(self) -> bool:
        row = self._connection.execute("SELECT 1 FROM tasks LIMIT 1").fetchone()
        return row is not None

    def _bootstrap_default_agents(self) -> bool:
        added = False
        with self._lock:
            for agent in build_default_agents():
                if self._load_agent(agent.agent_id) is None:
                    self._upsert_agent(agent)
                    added = True
        return added

    def _apply_seed_data(self) -> bool:
        if not self._seed_enabled:
            return False
        if self._seed_apply_if_empty and self._has_any_tasks():
            return False

        raw_seed = load_json_file(self._seed_file, default_factory=dict)
        if not isinstance(raw_seed, dict):
            return False

        changed = False
        with self._lock:
            for agent_payload in raw_seed.get("agents", []):
                if self._merge_seed_agent(agent_payload):
                    changed = True
            for task_payload in raw_seed.get("tasks", []):
                if self._merge_seed_task(task_payload):
                    changed = True
        return changed

    def _merge_seed_agent(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False

        if isinstance(payload.get("agent_id"), str):
            agent_id = payload["agent_id"]
            if self._load_agent(agent_id) is not None:
                return False
            self._upsert_agent(Agent.model_validate(payload))
            return True

        register_payload = AgentRegister.model_validate(payload)
        existing = self._find_existing_agent_by_signature(
            name=register_payload.name,
            role=register_payload.role,
            skills=register_payload.skills,
        )
        if existing is not None:
            return False
        generated_agent = Agent(
            agent_id=f"agent_{uuid4().hex[:8]}",
            name=register_payload.name,
            role=register_payload.role,
            skills=register_payload.skills,
            metadata=register_payload.metadata,
        )
        self._upsert_agent(generated_agent)
        return True

    def _find_existing_agent_by_signature(self, *, name: str, role: str, skills: list[str]) -> Agent | None:
        normalized_name = name.strip().lower()
        normalized_role = role.strip().lower()
        normalized_skills = sorted({skill.strip().lower() for skill in skills if skill.strip()})
        for agent in self._load_all_agents():
            agent_name = agent.name.strip().lower()
            agent_role = agent.role.strip().lower()
            agent_skills = sorted({skill.strip().lower() for skill in agent.skills if skill.strip()})
            if agent_name == normalized_name and agent_role == normalized_role and agent_skills == normalized_skills:
                return agent
        return None

    def _merge_seed_task(self, payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False

        if isinstance(payload.get("task_id"), str):
            task_id = payload["task_id"]
            if self._load_task(task_id) is not None:
                return False
            self._upsert_task(Task.model_validate(payload))
            return True

        create_payload = TaskCreate.model_validate(payload)
        generated_task = Task(
            task_id=f"task_{uuid4().hex[:8]}",
            objective=create_payload.objective,
            priority=create_payload.priority,
            metadata=create_payload.metadata,
        )
        self._upsert_task(generated_task)
        return True

    def create_task(
        self,
        payload: TaskCreate,
        *,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
    ) -> Task:
        with self._lock:
            task = Task(
                task_id=f"task_{uuid4().hex[:8]}",
                owner_user_id=owner_user_id,
                owner_username=owner_username,
                objective=payload.objective,
                priority=payload.priority,
                metadata=payload.metadata,
            )
            self._upsert_task(task)
            return task

    def get_task(self, task_id: str) -> Task | None:
        with self._lock:
            return self._load_task(task_id)

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return self._load_all_tasks()

    def assign_workflow_context(
        self,
        task_id: str,
        assigned_agent_ids: list[str],
        decomposition: dict[str, Any],
        routing_explanation: dict[str, Any] | None = None,
    ) -> Task | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task:
                return None
            task.assigned_agent_ids = list(assigned_agent_ids)
            task.metadata["decomposition"] = decomposition
            if routing_explanation is not None:
                task.metadata["routing"] = routing_explanation
            task.updated_at = datetime.now(timezone.utc)
            self._upsert_task(task)
            return task

    def update_workflow_decomposition(self, task_id: str, decomposition: dict[str, Any]) -> Task | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task:
                return None
            task.metadata["decomposition"] = decomposition
            task.updated_at = datetime.now(timezone.utc)
            self._upsert_task(task)
            return task

    def update_task_status(self, task_id: str, update: TaskStatusUpdate) -> Task | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task:
                return None

            previous_status = task.status
            task.status = update.status
            task.progress = update.progress
            if update.result is not None:
                task.result = update.result
                if update.agent_id:
                    task.proposals.append(
                        TaskProposal(
                            agent_id=update.agent_id,
                            result=update.result,
                            confidence=update.confidence,
                        )
                    )

            if task.status == TaskStatus.FAILED and previous_status != TaskStatus.FAILED:
                failure_reason = update.error_message
                if not failure_reason and update.result and isinstance(update.result.get("error"), str):
                    failure_reason = str(update.result.get("error"))
                task.attempt_history.append(
                    TaskAttemptRecord(
                        attempt_number=task.retry_count + 1,
                        outcome="failed",
                        reason=failure_reason,
                        error_code=update.error_code,
                    )
                )

            if task.status == TaskStatus.COMPLETED and previous_status != TaskStatus.COMPLETED:
                task.attempt_history.append(
                    TaskAttemptRecord(
                        attempt_number=task.retry_count + 1,
                        outcome="completed",
                    )
                )

            task.updated_at = datetime.now(timezone.utc)
            self._upsert_task(task)
            return task

    def set_task_consensus(self, task_id: str, consensus: TaskConsensus) -> Task | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task:
                return None
            task.consensus = consensus
            task.result = consensus.decision_result
            task.updated_at = datetime.now(timezone.utc)
            self._upsert_task(task)
            return task

    def get_task_result(self, task_id: str) -> TaskResultResponse | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task:
                return None
            return TaskResultResponse(
                task_id=task.task_id,
                status=task.status,
                result=task.result,
                consensus=task.consensus,
                updated_at=task.updated_at,
            )

    def register_agent(self, payload: AgentRegister) -> Agent:
        with self._lock:
            existing = self._find_existing_agent_by_signature(
                name=payload.name,
                role=payload.role,
                skills=payload.skills,
            )
            if existing is not None:
                return existing
            agent = Agent(
                agent_id=f"agent_{uuid4().hex[:8]}",
                name=payload.name,
                role=payload.role,
                skills=payload.skills,
                metadata=payload.metadata,
            )
            self._upsert_agent(agent)
            return agent

    def list_agents(self) -> list[Agent]:
        with self._lock:
            return self._load_all_agents()

    def get_agent(self, agent_id: str) -> Agent | None:
        with self._lock:
            return self._load_agent(agent_id)

    def update_agent_status(self, agent_id: str, status: AgentStatus) -> Agent | None:
        with self._lock:
            agent = self._load_agent(agent_id)
            if not agent:
                return None
            agent.status = status
            self._upsert_agent(agent)
            return agent

    def claim_task(self, task_id: str, agent_id: str) -> Task | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task:
                return None
            task.current_agent_id = agent_id
            task.updated_at = datetime.now(timezone.utc)
            self._upsert_task(task)
            return task

    def handoff_task(
        self,
        task_id: str,
        from_agent_id: str,
        to_agent_id: str,
        reason: str | None = None,
    ) -> Task | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task:
                return None
            task.current_agent_id = to_agent_id
            task.handoff_history.append(
                TaskHandoffRecord(
                    from_agent_id=from_agent_id,
                    to_agent_id=to_agent_id,
                    reason=reason,
                )
            )
            task.updated_at = datetime.now(timezone.utc)
            self._upsert_task(task)
            return task

    def retry_task(self, task_id: str, reason: str | None = None) -> Task | None:
        with self._lock:
            task = self._load_task(task_id)
            if not task or task.status != TaskStatus.FAILED:
                return None
            task.retry_count += 1
            task.last_retry_at = datetime.now(timezone.utc)
            task.attempt_history.append(
                TaskAttemptRecord(
                    attempt_number=task.retry_count,
                    outcome="retried",
                    reason=reason,
                )
            )
            task.status = TaskStatus.QUEUED
            task.progress = 0
            task.result = None
            task.consensus = None
            task.proposals = []
            task.current_agent_id = None
            if reason:
                task.metadata["last_retry_reason"] = reason
            task.updated_at = datetime.now(timezone.utc)
            self._upsert_task(task)
            return task

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            with self._connection:
                cursor = self._connection.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            return cursor.rowcount > 0

    def delete_tasks_by_owner(self, owner_user_id: str) -> int:
        with self._lock:
            owned_task_ids = [
                task.task_id
                for task in self._load_all_tasks()
                if task.owner_user_id == owner_user_id
            ]
            if not owned_task_ids:
                return 0
            with self._connection:
                for task_id in owned_task_ids:
                    self._connection.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            return len(owned_task_ids)

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            tasks = {task.task_id: task.model_dump(mode="json") for task in self._load_all_tasks()}
            agents = {agent.agent_id: agent.model_dump(mode="json") for agent in self._load_all_agents()}
            return {"tasks": tasks, "agents": agents}

    def import_snapshot(self, snapshot: dict[str, Any], *, keep_default_agents: bool = False) -> dict[str, int]:
        with self._lock:
            self._delete_all_tasks()
            self._delete_all_agents()
            if keep_default_agents:
                for agent in build_default_agents():
                    self._upsert_agent(agent)

            raw_agents = snapshot.get("agents", {}) if isinstance(snapshot, dict) else {}
            if isinstance(raw_agents, dict):
                for agent_payload in raw_agents.values():
                    if isinstance(agent_payload, dict):
                        self._upsert_agent(Agent.model_validate(agent_payload))

            raw_tasks = snapshot.get("tasks", {}) if isinstance(snapshot, dict) else {}
            if isinstance(raw_tasks, dict):
                for task_payload in raw_tasks.values():
                    if isinstance(task_payload, dict):
                        self._upsert_task(Task.model_validate(task_payload))

            return {
                "tasks": len(self._load_all_tasks()),
                "agents": len(self._load_all_agents()),
            }

    def clear(self, keep_default_agents: bool = True) -> None:
        with self._lock:
            self._delete_all_tasks()
            self._delete_all_agents()
            if keep_default_agents:
                for agent in build_default_agents():
                    self._upsert_agent(agent)

    def apply_seed_data(self) -> bool:
        return self._apply_seed_data()





