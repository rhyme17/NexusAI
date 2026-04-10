from ..models.task import Task
from .base import BaseAgent


class PlannerAgent(BaseAgent):
    name = "planner-agent"
    role = "planner"
    skills = ["plan", "breakdown", "workflow", "prioritize"]

    def execute(self, task: Task) -> dict[str, str]:
        return {
            "summary": f"Task plan created for: {task.objective}",
            "next_step": "dispatch_subtasks",
        }


