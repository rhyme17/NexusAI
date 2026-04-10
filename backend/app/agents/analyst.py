from ..models.task import Task
from .base import BaseAgent


class AnalystAgent(BaseAgent):
    name = "analyst-agent"
    role = "analyst"
    skills = ["analysis", "risk", "evaluation", "insight"]

    def execute(self, task: Task) -> dict[str, str]:
        return {
            "summary": f"Analysis completed for: {task.objective}",
            "artifact": "analysis_notes",
        }

