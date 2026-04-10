from ..models.task import Task
from .base import BaseAgent


class WriterAgent(BaseAgent):
    name = "writer-agent"
    role = "writer"
    skills = ["write", "summary", "report", "edit"]

    def execute(self, task: Task) -> dict[str, str]:
        return {
            "summary": f"Draft report generated for: {task.objective}",
            "artifact": "draft_report",
        }

