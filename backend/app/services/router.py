from __future__ import annotations

import re
from typing import Any

from ..core.config import resolve_router_policy
from ..models.agent import Agent, AgentStatus
from ..models.task import Task


class TaskRouter:
    """Baseline router using skill overlap, agent status, and lightweight load hints."""

    _TOKEN_PATTERN = re.compile(r"[\w\-]{2,}")
    _STATUS_RANK = {
        AgentStatus.ONLINE: 2,
        AgentStatus.BUSY: 1,
        AgentStatus.OFFLINE: 0,
    }

    def __init__(self, policy_override: dict[str, Any] | None = None) -> None:
        self._policy_override = policy_override or {}

    def pick_agents(self, task: Task, agents: list[Agent], limit: int = 2) -> list[str]:
        selected, _ = self.route_task(task, agents, limit=limit)
        return selected

    def route_task(self, task: Task, agents: list[Agent], limit: int = 2) -> tuple[list[str], dict[str, Any]]:
        keywords = self._extract_keywords(task.objective)
        preferred_roles = self._preferred_roles(task.objective)
        policy = self._resolve_policy(task)
        priority_level = task.priority.value
        status_weight = int(policy["status_weight"]) + int(policy["priority_status_bonus"][priority_level])
        if not agents:
            return [], {
                "strategy": "keyword_skill_status_load",
                "objective_keywords": keywords,
                "priority": priority_level,
                "policy": policy,
                "selected_agent_ids": [],
                "reason": "No agents available for routing.",
                "candidates": [],
            }

        candidates: list[dict[str, Any]] = []
        for agent in agents:
            matched_skills = sorted(
                {
                    skill
                    for skill in agent.skills
                    if skill.lower() in keywords or any(keyword in skill.lower() for keyword in keywords)
                }
            )
            status_rank = self._STATUS_RANK.get(agent.status, 0)
            active_task_count = self._coerce_active_task_count(agent.metadata.get("active_task_count"))
            skill_score = len(matched_skills)
            role_score = self._role_priority_score(agent.role, preferred_roles)
            if skill_score == 0:
                role_score *= 1000
            total_score = (
                skill_score * int(policy["skill_weight"])
                + role_score
                + status_rank * status_weight
                - active_task_count * int(policy["load_penalty"])
            )
            candidates.append(
                {
                    "agent_id": agent.agent_id,
                    "role": agent.role,
                    "status": agent.status.value,
                    "matched_skills": matched_skills,
                    "skill_score": skill_score,
                    "role_score": role_score,
                    "status_rank": status_rank,
                    "active_task_count": active_task_count,
                    "score_breakdown": {
                        "skill_component": skill_score * int(policy["skill_weight"]),
                        "role_component": role_score,
                        "status_component": status_rank * status_weight,
                        "load_penalty_component": active_task_count * int(policy["load_penalty"]),
                        "effective_status_weight": status_weight,
                        "priority": priority_level,
                    },
                    "total_score": total_score,
                }
            )

        ranked = sorted(
            candidates,
            key=lambda item: (
                -int(item["total_score"]),
                -int(item["skill_score"]),
                -int(item["status_rank"]),
                int(item["active_task_count"]),
                str(item["agent_id"]),
            ),
        )
        selected = [str(item["agent_id"]) for item in ranked[:limit]]

        for index, item in enumerate(ranked, start=1):
            item["rank"] = index
            item["selected"] = str(item["agent_id"]) in selected
            item["selection_reason"] = self._build_selection_reason(item)

        explanation = {
            "strategy": "keyword_skill_status_load",
            "objective_keywords": keywords,
            "priority": priority_level,
            "policy": policy,
            "selected_agent_ids": selected,
            "reason": self._build_routing_reason(ranked, selected),
            "candidates": ranked,
        }
        return selected, explanation

    def _resolve_policy(self, task: Task) -> dict[str, Any]:
        base_policy = resolve_router_policy(task.metadata if isinstance(task.metadata, dict) else None)
        if not self._policy_override:
            return base_policy
        merged = dict(base_policy)
        merged.update({k: v for k, v in self._policy_override.items() if k != "priority_status_bonus"})
        if "priority_status_bonus" in self._policy_override and isinstance(self._policy_override["priority_status_bonus"], dict):
            merged_bonus = dict(base_policy.get("priority_status_bonus", {}))
            merged_bonus.update(self._policy_override["priority_status_bonus"])
            merged["priority_status_bonus"] = merged_bonus
        return merged

    def _extract_keywords(self, objective: str) -> list[str]:
        return sorted({token.lower() for token in self._TOKEN_PATTERN.findall(objective)})

    @staticmethod
    def _coerce_active_task_count(value: object) -> int:
        if not isinstance(value, (int, str, float)):
            return 0
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _build_selection_reason(item: dict[str, Any]) -> str:
        matched_skills = item.get("matched_skills") or []
        if matched_skills:
            return (
                f"Matched skills {matched_skills}; status={item['status']}; "
                f"active_task_count={item['active_task_count']}."
            )
        return (
            f"No direct skill hit; fell back to agent availability with status={item['status']} "
            f"and active_task_count={item['active_task_count']}."
        )

    @staticmethod
    def _build_routing_reason(ranked: list[dict[str, Any]], selected: list[str]) -> str:
        if not ranked:
            return "No routing candidates were available."
        if any(item.get("skill_score", 0) for item in ranked):
            return f"Selected {selected} using skill overlap first, then status and active task count as tie-breakers."
        return f"No direct skill overlap found; selected {selected} using agent availability and low active task count."

    @staticmethod
    def _preferred_roles(objective: str) -> list[str]:
        normalized = objective.strip().lower()
        report_keywords = ["report", "research", "analysis", "summary", "调研", "研究", "报告", "分析"]
        planning_keywords = ["plan", "roadmap", "milestone", "timeline", "计划", "方案", "路线图"]
        if any(keyword in normalized for keyword in report_keywords):
            return ["writer", "analyst", "research", "reviewer", "planner"]
        if any(keyword in normalized for keyword in planning_keywords):
            return ["planner", "analyst", "writer", "research"]
        return ["planner", "analyst", "writer", "research", "reviewer", "judge"]

    @staticmethod
    def _role_priority_score(role: str, preferred_roles: list[str]) -> int:
        normalized = role.strip().lower()
        if normalized in preferred_roles:
            return (len(preferred_roles) - preferred_roles.index(normalized)) * 3
        return 0


