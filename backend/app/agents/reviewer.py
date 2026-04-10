from ..models.task import Task
from .base import BaseAgent


class ReviewerAgent(BaseAgent):
    name = "reviewer-agent"
    role = "reviewer"
    skills = ["review", "quality", "consistency", "validation"]

    def execute(self, task: Task) -> dict[str, str]:
        return {
            "summary": f"Quality review prepared for: {task.objective}",
            "artifact": "review_feedback",
        }

