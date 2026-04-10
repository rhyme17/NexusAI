from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.agent import Agent, AgentRegister, AgentStatus
from ..models.task import Task, TaskConsensus, TaskCreate, TaskResultResponse, TaskStatusUpdate


class StoreContract(ABC):
    """Minimal storage interface consumed by orchestration services."""

    @abstractmethod
    def create_task(
        self,
        payload: TaskCreate,
        *,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
    ) -> Task: ...

    @abstractmethod
    def get_task(self, task_id: str) -> Task | None: ...

    @abstractmethod
    def list_tasks(self) -> list[Task]: ...

    @abstractmethod
    def assign_workflow_context(
        self,
        task_id: str,
        assigned_agent_ids: list[str],
        decomposition: dict[str, Any],
        routing_explanation: dict[str, Any] | None = None,
    ) -> Task | None: ...

    @abstractmethod
    def update_workflow_decomposition(self, task_id: str, decomposition: dict[str, Any]) -> Task | None: ...

    @abstractmethod
    def update_task_status(self, task_id: str, update: TaskStatusUpdate) -> Task | None: ...

    @abstractmethod
    def set_task_consensus(self, task_id: str, consensus: TaskConsensus) -> Task | None: ...

    @abstractmethod
    def get_task_result(self, task_id: str) -> TaskResultResponse | None: ...

    @abstractmethod
    def register_agent(self, payload: AgentRegister) -> Agent: ...

    @abstractmethod
    def list_agents(self) -> list[Agent]: ...

    @abstractmethod
    def get_agent(self, agent_id: str) -> Agent | None: ...

    @abstractmethod
    def update_agent_status(self, agent_id: str, status: AgentStatus) -> Agent | None: ...

    @abstractmethod
    def claim_task(self, task_id: str, agent_id: str) -> Task | None: ...

    @abstractmethod
    def handoff_task(
        self,
        task_id: str,
        from_agent_id: str,
        to_agent_id: str,
        reason: str | None = None,
    ) -> Task | None: ...

    @abstractmethod
    def retry_task(self, task_id: str, reason: str | None = None) -> Task | None: ...

    @abstractmethod
    def delete_task(self, task_id: str) -> bool: ...

    @abstractmethod
    def delete_tasks_by_owner(self, owner_user_id: str) -> int: ...

    @abstractmethod
    def export_snapshot(self) -> dict[str, Any]: ...

    @abstractmethod
    def import_snapshot(self, snapshot: dict[str, Any], *, keep_default_agents: bool = False) -> dict[str, int]: ...

    @abstractmethod
    def clear(self, keep_default_agents: bool = True) -> None: ...

    @abstractmethod
    def apply_seed_data(self) -> bool: ...

