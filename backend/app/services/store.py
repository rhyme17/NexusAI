from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from ..core.config import (
    get_agents_file,
    get_postgres_dsn,
    get_seed_file,
    get_sqlite_path,
    get_storage_backend,
    get_storage_fallback_backend,
    get_tasks_file,
    is_json_persistence_enabled,
    is_seed_apply_if_empty,
    is_seed_enabled,
    should_fallback_on_storage_error,
)
from ..agents import build_default_agents
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
from .json_persistence import load_json_file, write_json_file_atomic
from .postgres_store import PostgresStore
from .sqlite_store import SQLiteStore
from .store_contract import StoreContract


_LOGGER = logging.getLogger("nexusai.store")


class InMemoryStore(StoreContract):
    """In-memory storage for the current baseline stage; can be replaced by a DB repository later."""

    def __init__(
        self,
        *,
        persistence_enabled: bool | None = None,
        tasks_file: Path | None = None,
        agents_file: Path | None = None,
    ) -> None:
        self._tasks: dict[str, Task] = {}
        self._agents: dict[str, Agent] = {}
        self._lock = Lock()
        self._persistence_enabled = is_json_persistence_enabled() if persistence_enabled is None else persistence_enabled
        self._tasks_file = tasks_file or get_tasks_file()
        self._agents_file = agents_file or get_agents_file()
        self._seed_file = get_seed_file()
        self._seed_enabled = is_seed_enabled()
        self._seed_apply_if_empty = is_seed_apply_if_empty()
        self._load_agents()
        self._load_tasks()
        defaults_added = self._bootstrap_default_agents()
        seeded = self._apply_seed_data()
        if defaults_added:
            self._persist_agents()
        if seeded:
            self._persist_agents()
            self._persist_tasks()

    def _bootstrap_default_agents(self) -> bool:
        added = False
        defaults = build_default_agents()
        for agent in defaults:
            if agent.agent_id not in self._agents:
                self._agents[agent.agent_id] = agent
                added = True
        return added

    def _load_tasks(self) -> None:
        if not self._persistence_enabled:
            return
        raw_tasks = load_json_file(self._tasks_file, default_factory=dict)
        if not isinstance(raw_tasks, dict):
            return
        self._tasks = {
            task_id: Task.model_validate(task_payload)
            for task_id, task_payload in raw_tasks.items()
            if isinstance(task_id, str) and isinstance(task_payload, dict)
        }

    def _load_agents(self) -> None:
        if not self._persistence_enabled:
            return
        raw_agents = load_json_file(self._agents_file, default_factory=dict)
        if not isinstance(raw_agents, dict):
            return
        self._agents = {
            agent_id: Agent.model_validate(agent_payload)
            for agent_id, agent_payload in raw_agents.items()
            if isinstance(agent_id, str) and isinstance(agent_payload, dict)
        }

    def _persist_tasks(self) -> None:
        if not self._persistence_enabled:
            return
        write_json_file_atomic(
            self._tasks_file,
            {task_id: task.model_dump(mode="json") for task_id, task in self._tasks.items()},
        )

    def _persist_agents(self) -> None:
        if not self._persistence_enabled:
            return
        write_json_file_atomic(
            self._agents_file,
            {agent_id: agent.model_dump(mode="json") for agent_id, agent in self._agents.items()},
        )

    def _apply_seed_data(self) -> bool:
        if not self._seed_enabled:
            return False
        if self._seed_apply_if_empty and self._tasks:
            return False

        raw_seed = load_json_file(self._seed_file, default_factory=dict)
        if not isinstance(raw_seed, dict):
            return False

        changed = False
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
            if agent_id in self._agents:
                return False
            self._agents[agent_id] = Agent.model_validate(payload)
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
        self._agents[generated_agent.agent_id] = generated_agent
        return True

    def _find_existing_agent_by_signature(self, *, name: str, role: str, skills: list[str]) -> Agent | None:
        normalized_name = name.strip().lower()
        normalized_role = role.strip().lower()
        normalized_skills = sorted({skill.strip().lower() for skill in skills if skill.strip()})
        for agent in self._agents.values():
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
            if task_id in self._tasks:
                return False
            self._tasks[task_id] = Task.model_validate(payload)
            return True

        create_payload = TaskCreate.model_validate(payload)
        generated_task = Task(
            task_id=f"task_{uuid4().hex[:8]}",
            objective=create_payload.objective,
            priority=create_payload.priority,
            metadata=create_payload.metadata,
        )
        self._tasks[generated_task.task_id] = generated_task
        return True

    def create_task(
        self,
        payload: TaskCreate,
        *,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
    ) -> Task:
        with self._lock:
            task_id = f"task_{uuid4().hex[:8]}"
            task = Task(
                task_id=task_id,
                owner_user_id=owner_user_id,
                owner_username=owner_username,
                objective=payload.objective,
                priority=payload.priority,
                metadata=payload.metadata,
            )
            self._tasks[task_id] = task
            self._persist_tasks()
            return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def assign_workflow_context(
        self,
        task_id: str,
        assigned_agent_ids: list[str],
        decomposition: dict[str, Any],
        routing_explanation: dict[str, Any] | None = None,
    ) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.assigned_agent_ids = list(assigned_agent_ids)
            task.metadata["decomposition"] = decomposition
            if routing_explanation is not None:
                task.metadata["routing"] = routing_explanation
            task.updated_at = datetime.now(timezone.utc)
            self._persist_tasks()
            return task

    def update_workflow_decomposition(self, task_id: str, decomposition: dict[str, Any]) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.metadata["decomposition"] = decomposition
            task.updated_at = datetime.now(timezone.utc)
            self._persist_tasks()
            return task

    def update_task_status(self, task_id: str, update: TaskStatusUpdate) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
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
                    failure_reason = update.result.get("error")
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
            self._persist_tasks()
            return task

    def set_task_consensus(self, task_id: str, consensus: TaskConsensus) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            task.consensus = consensus
            task.result = consensus.decision_result
            task.updated_at = datetime.now(timezone.utc)
            self._persist_tasks()
            return task

    def get_task_result(self, task_id: str) -> TaskResultResponse | None:
        task = self._tasks.get(task_id)
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
            agent_id = f"agent_{uuid4().hex[:8]}"
            agent = Agent(
                agent_id=agent_id,
                name=payload.name,
                role=payload.role,
                skills=payload.skills,
                metadata=payload.metadata,
            )
            self._agents[agent_id] = agent
            self._persist_agents()
            return agent

    def list_agents(self) -> list[Agent]:
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def update_agent_status(self, agent_id: str, status: AgentStatus) -> Agent | None:
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return None
            agent.status = status
            self._persist_agents()
            return agent

    def claim_task(self, task_id: str, agent_id: str) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.current_agent_id = agent_id
            task.updated_at = datetime.now(timezone.utc)
            self._persist_tasks()
            return task

    def handoff_task(
        self,
        task_id: str,
        from_agent_id: str,
        to_agent_id: str,
        reason: str | None = None,
    ) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
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
            self._persist_tasks()
            return task

    def retry_task(self, task_id: str, reason: str | None = None) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
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
            self._persist_tasks()
            return task

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            removed = self._tasks.pop(task_id, None)
            if removed is None:
                return False
            self._persist_tasks()
            return True

    def delete_tasks_by_owner(self, owner_user_id: str) -> int:
        with self._lock:
            task_ids = [
                task_id
                for task_id, task in self._tasks.items()
                if task.owner_user_id == owner_user_id
            ]
            for task_id in task_ids:
                self._tasks.pop(task_id, None)
            if task_ids:
                self._persist_tasks()
            return len(task_ids)

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tasks": {task_id: task.model_dump(mode="json") for task_id, task in self._tasks.items()},
                "agents": {agent_id: agent.model_dump(mode="json") for agent_id, agent in self._agents.items()},
            }

    def import_snapshot(self, snapshot: dict[str, Any], *, keep_default_agents: bool = False) -> dict[str, int]:
        with self._lock:
            self._tasks = {}
            self._agents = {}
            if keep_default_agents:
                self._bootstrap_default_agents()

            raw_agents = snapshot.get("agents", {}) if isinstance(snapshot, dict) else {}
            if isinstance(raw_agents, dict):
                for agent_id, agent_payload in raw_agents.items():
                    if isinstance(agent_id, str) and isinstance(agent_payload, dict):
                        self._agents[agent_id] = Agent.model_validate(agent_payload)

            raw_tasks = snapshot.get("tasks", {}) if isinstance(snapshot, dict) else {}
            if isinstance(raw_tasks, dict):
                for task_id, task_payload in raw_tasks.items():
                    if isinstance(task_id, str) and isinstance(task_payload, dict):
                        self._tasks[task_id] = Task.model_validate(task_payload)

            self._persist_agents()
            self._persist_tasks()
            return {"tasks": len(self._tasks), "agents": len(self._agents)}

    def clear(self, keep_default_agents: bool = True) -> None:
        with self._lock:
            self._tasks = {}
            self._agents = {}
            if keep_default_agents:
                self._bootstrap_default_agents()
            self._persist_tasks()
            self._persist_agents()

    def apply_seed_data(self) -> bool:
        with self._lock:
            changed = self._apply_seed_data()
            if changed:
                self._persist_agents()
                self._persist_tasks()
            return changed


_store: Any | None = None
_store_signature: tuple[str, ...] | None = None


def _build_store_signature() -> tuple[str, ...]:
    backend = get_storage_backend()
    if backend == "sqlite":
        return (backend, str(get_sqlite_path()))
    if backend == "postgres":
        return (
            backend,
            str(get_postgres_dsn()),
            str(should_fallback_on_storage_error()),
            get_storage_fallback_backend(),
            str(get_sqlite_path()),
            str(get_tasks_file()),
            str(get_agents_file()),
            str(is_json_persistence_enabled()),
        )
    return (
        backend,
        str(get_tasks_file()),
        str(get_agents_file()),
        str(is_json_persistence_enabled()),
    )


def _create_store() -> Any:
    backend = get_storage_backend()
    if backend == "sqlite":
        return SQLiteStore(sqlite_path=get_sqlite_path())
    if backend == "postgres":
        try:
            return PostgresStore(dsn=get_postgres_dsn())
        except Exception:
            if not should_fallback_on_storage_error():
                raise
            fallback_backend = get_storage_fallback_backend()
            _LOGGER.warning(
                "Postgres store init failed; falling back to %s backend",
                fallback_backend,
                exc_info=True,
            )
            if fallback_backend == "sqlite":
                return SQLiteStore(sqlite_path=get_sqlite_path())
            return InMemoryStore()
    return InMemoryStore()


def get_store() -> Any:
    global _store, _store_signature
    signature = _build_store_signature()
    if _store is None or _store_signature != signature:
        _store = _create_store()
        _store_signature = signature
    return _store
