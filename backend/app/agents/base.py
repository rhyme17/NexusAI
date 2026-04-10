from abc import ABC, abstractmethod
from typing import Any

from ..models.agent import Agent
from ..models.task import Task


class BaseAgent(ABC):
    """Agent interface for future pluggable implementations."""

    name: str
    role: str
    skills: list[str]

    @abstractmethod
    def execute(self, task: Task) -> dict[str, Any]:
        raise NotImplementedError

    def to_agent_model(self, agent_id: str) -> Agent:
        """Project-level adapter so registry storage can stay model-driven."""
        return Agent(
            agent_id=agent_id,
            name=self.name,
            role=self.role,
            skills=self.skills,
            metadata={"source": "predefined"},
        )


