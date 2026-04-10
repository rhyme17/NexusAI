"""Agent abstractions and predefined implementations."""

from ..models.agent import Agent
from .analyst import AnalystAgent
from .judge import JudgeAgent
from .planner import PlannerAgent
from .research import ResearchAgent
from .reviewer import ReviewerAgent
from .writer import WriterAgent


def build_default_agents() -> list[Agent]:
    defaults = [
        ("agent_planner", PlannerAgent()),
        ("agent_research", ResearchAgent()),
        ("agent_writer", WriterAgent()),
        ("agent_analyst", AnalystAgent()),
        ("agent_reviewer", ReviewerAgent()),
        ("agent_judge", JudgeAgent()),
    ]
    return [agent.to_agent_model(agent_id) for agent_id, agent in defaults]

