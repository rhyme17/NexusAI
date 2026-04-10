import { describe, expect, it } from "vitest";

import type { TaskDecomposition } from "@/lib/api/types";
import { buildTaskFlowLayout, buildTaskFlowSteps } from "./task-flow-helpers";

describe("task-flow-helpers", () => {
  it("prefers dag_nodes and maps dispatch state to flow status", () => {
    const decomposition: TaskDecomposition = {
      mode: "mvp_linear",
      subtasks: [
        {
          step_id: "s1",
          title: "subtask-one",
          status: "queued",
          assigned_agent_id: null,
          depends_on: []
        }
      ],
      dag_nodes: [
        {
          node_id: "n1",
          title: "dag-root",
          status: "queued",
          dispatch_state: "running",
          assigned_agent_id: "agent_a",
          depends_on: []
        },
        {
          node_id: "n2",
          title: "dag-child",
          status: "queued",
          dispatch_state: "blocked",
          assigned_agent_id: "agent_b",
          depends_on: ["n1"]
        }
      ]
    };

    const steps = buildTaskFlowSteps(decomposition);
    expect(steps).toHaveLength(2);
    expect(steps[0].id).toBe("n1");
    expect(steps[0].status).toBe("in_progress");
    expect(steps[1].status).toBe("queued");
  });

  it("builds dependency-aware layout and ignores invalid dependencies", () => {
    const decomposition: TaskDecomposition = {
      mode: "mvp_linear",
      subtasks: [
        {
          step_id: "step_1",
          title: "Root",
          status: "completed",
          assigned_agent_id: "agent_planner",
          depends_on: []
        },
        {
          step_id: "step_2",
          title: "Middle",
          status: "in_progress",
          assigned_agent_id: "agent_research",
          depends_on: ["step_1", "missing_step"]
        },
        {
          step_id: "step_3",
          title: "Leaf",
          status: "queued",
          assigned_agent_id: "agent_writer",
          depends_on: ["step_2", "step_2"]
        }
      ]
    };

    const steps = buildTaskFlowSteps(decomposition);
    const layout = buildTaskFlowLayout(steps);

    const nodeById = new Map(layout.nodes.map((node) => [node.id, node]));
    expect(nodeById.get("step_2")?.x).toBeGreaterThan(nodeById.get("step_1")?.x ?? 0);
    expect(nodeById.get("step_3")?.x).toBeGreaterThan(nodeById.get("step_2")?.x ?? 0);

    expect(layout.edges.map((edge) => edge.id)).toEqual(["step_1->step_2", "step_2->step_3"]);
    expect(layout.edges.find((edge) => edge.id === "step_1->step_2")?.animated).toBe(true);
  });

  it("keeps cyclic nodes renderable by placing them in fallback columns", () => {
    const decomposition: TaskDecomposition = {
      mode: "mvp_linear",
      subtasks: [
        {
          step_id: "a",
          title: "A",
          status: "queued",
          assigned_agent_id: null,
          depends_on: ["b"]
        },
        {
          step_id: "b",
          title: "B",
          status: "queued",
          assigned_agent_id: null,
          depends_on: ["a"]
        }
      ]
    };

    const layout = buildTaskFlowLayout(buildTaskFlowSteps(decomposition));
    expect(layout.nodes).toHaveLength(2);
    expect(layout.edges).toHaveLength(2);
    expect(layout.nodes.every((node) => Number.isFinite(node.x) && Number.isFinite(node.y))).toBe(true);
  });
});

