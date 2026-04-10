from ..models.task import Task
from .base import BaseAgent


class ResearchAgent(BaseAgent):
    name = "research-agent"
    role = "research"
    skills = ["research", "search", "analysis", "sources"]

    def execute(self, task: Task) -> dict[str, str]:
        return {
            "summary": f"Research notes collected for: {task.objective}",
            "artifact": "research_brief",
        }

