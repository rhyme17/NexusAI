from __future__ import annotations

from collections import Counter
from typing import Any

from ..models.task import Task, TaskConsensus


class ConsensusService:
    """Rule-based consensus for the current baseline stage."""

    def evaluate(self, task: Task, strategy: str = "highest_confidence") -> TaskConsensus | None:
        if len(task.proposals) < 2:
            return None

        proposal_views = [
            {
                "normalized": self._normalize_result(proposal.result),
                "confidence": proposal.confidence,
                "result": proposal.result,
                "agent_id": proposal.agent_id,
                "summary": str(proposal.result.get("summary", "")),
            }
            for proposal in task.proposals
        ]

        unique_views = {str(item["normalized"]) for item in proposal_views}
        has_conflict = len(unique_views) > 1
        view_counts = Counter(str(item["normalized"]) for item in proposal_views)

        if strategy == "majority_vote":
            best = self._majority_vote(proposal_views)
            decided_by = "majority_vote"
        else:
            best = max(proposal_views, key=lambda item: float(item["confidence"]))
            decided_by = "highest_confidence"

        if has_conflict:
            if decided_by == "majority_vote":
                reason = (
                    f"Conflict detected across {len(task.proposals)} proposals; majority vote selected "
                    f"agent {best['agent_id']} with confidence tie-break."
                )
            else:
                reason = (
                    f"Conflict detected across {len(task.proposals)} proposals; highest confidence selected "
                    f"agent {best['agent_id']}."
                )
        else:
            reason = f"No conflict detected; {len(task.proposals)} agent proposals are consistent."

        explanation: dict[str, Any] = {
            "strategy": decided_by,
            "proposal_count": len(task.proposals),
            "unique_view_count": len(unique_views),
            "selected_agent_id": best["agent_id"],
            "selected_confidence": best["confidence"],
            "selected_summary": best["summary"],
            "comparison_basis": (
                "majority count with confidence tie-break"
                if decided_by == "majority_vote"
                else "highest confidence"
            ),
            "views": [
                {
                    "agent_id": item["agent_id"],
                    "summary": item["summary"],
                    "confidence": item["confidence"],
                    "count": view_counts[str(item["normalized"])],
                }
                for item in proposal_views
            ],
        }
        if has_conflict:
            explanation["conflicting_agent_ids"] = [
                str(item["agent_id"])
                for item in proposal_views
                if str(item["normalized"]) != str(best["normalized"])
            ]

        return TaskConsensus(
            conflict_detected=has_conflict,
            decision_result=dict(best["result"]),
            decided_by=decided_by,
            reason=reason,
            explanation=explanation,
        )

    def _majority_vote(
        self,
        proposal_views: list[dict[str, Any]],
    ) -> dict[str, Any]:
        view_counts = Counter([str(item["normalized"]) for item in proposal_views])
        winner_count = max(view_counts.values())
        winner_views = {view for view, count in view_counts.items() if count == winner_count}

        winners = [item for item in proposal_views if str(item["normalized"]) in winner_views]
        return max(winners, key=lambda item: float(item["confidence"]))

    def _normalize_result(self, result: dict) -> str:
        summary = result.get("summary")
        if isinstance(summary, str):
            return summary.strip().lower()
        return str(result).strip().lower()



