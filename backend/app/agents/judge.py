from ..models.task import Task
from .base import BaseAgent


class JudgeAgent(BaseAgent):
    name = "judge-agent"
    role = "judge"
    skills = ["arbitration", "decision", "conflict_resolution", "consensus"]

    def execute(self, task: Task) -> dict[str, str]:
        return {
            "summary": f"Arbitration decision prepared for: {task.objective}",
            "artifact": "judge_decision",
        }

