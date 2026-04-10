import { TaskDagNode, TaskDecomposition, TaskSubtask } from "@/lib/api/types";

export interface TaskFlowStep {
  id: string;
  title: string;
  assignedAgentId: string | null;
  status: string;
  dependsOn: string[];
}

export interface TaskFlowLayoutNode {
  id: string;
  x: number;
  y: number;
  borderColor: string;
  step: TaskFlowStep;
}

export interface TaskFlowLayoutEdge {
  id: string;
  source: string;
  target: string;
  animated: boolean;
}

export interface TaskFlowLayout {
  nodes: TaskFlowLayoutNode[];
  edges: TaskFlowLayoutEdge[];
}

const STATUS_COLOR_MAP: Record<string, string> = {
  queued: "#a39d8f",
  in_progress: "#d97757",
  completed: "#3f6b4a",
  failed: "#c0453a"
};

export function buildTaskFlowSteps(decomposition: TaskDecomposition): TaskFlowStep[] {
  const source = decomposition.dag_nodes && decomposition.dag_nodes.length > 0
    ? decomposition.dag_nodes
    : decomposition.subtasks;

  const steps = source.map((item) => toTaskFlowStep(item));
  const seen = new Set<string>();
  return steps.filter((step) => {
    if (seen.has(step.id)) {
      return false;
    }
    seen.add(step.id);
    return true;
  });
}

export function buildTaskFlowLayout(steps: TaskFlowStep[]): TaskFlowLayout {
  if (steps.length === 0) {
    return { nodes: [], edges: [] };
  }

  const indexById = new Map<string, number>();
  steps.forEach((step, index) => indexById.set(step.id, index));

  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  const edges: TaskFlowLayoutEdge[] = [];
  const edgeSet = new Set<string>();

  steps.forEach((step) => {
    inDegree.set(step.id, 0);
    adjacency.set(step.id, []);
  });

  steps.forEach((step) => {
    getValidDependencies(step, indexById).forEach((dependency) => {
      const edgeId = `${dependency}->${step.id}`;
      if (edgeSet.has(edgeId)) {
        return;
      }
      edgeSet.add(edgeId);
      adjacency.get(dependency)?.push(step.id);
      inDegree.set(step.id, (inDegree.get(step.id) ?? 0) + 1);
      edges.push({
        id: edgeId,
        source: dependency,
        target: step.id,
        animated: step.status === "in_progress"
      });
    });
  });

  const levels = new Map<string, number>();
  const queue: string[] = steps
    .filter((step) => (inDegree.get(step.id) ?? 0) === 0)
    .sort((a, b) => (indexById.get(a.id) ?? 0) - (indexById.get(b.id) ?? 0))
    .map((step) => step.id);

  queue.forEach((id) => levels.set(id, 0));

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      continue;
    }
    const currentLevel = levels.get(current) ?? 0;

    (adjacency.get(current) ?? []).forEach((nextId) => {
      levels.set(nextId, Math.max(levels.get(nextId) ?? 0, currentLevel + 1));
      const remaining = (inDegree.get(nextId) ?? 0) - 1;
      inDegree.set(nextId, remaining);
      if (remaining === 0) {
        queue.push(nextId);
      }
    });
  }

  const fallbackLevel = Math.max(0, ...Array.from(levels.values(), (value) => value));
  steps.forEach((step) => {
    if (!levels.has(step.id)) {
      levels.set(step.id, fallbackLevel + 1);
    }
  });

  const levelsMap = new Map<number, TaskFlowStep[]>();
  steps.forEach((step) => {
    const level = levels.get(step.id) ?? 0;
    const bucket = levelsMap.get(level) ?? [];
    bucket.push(step);
    levelsMap.set(level, bucket);
  });

  const nodes: TaskFlowLayoutNode[] = Array.from(levelsMap.entries())
    .sort((a, b) => a[0] - b[0])
    .flatMap(([level, levelSteps]) => {
      return levelSteps
        .sort((left, right) => (indexById.get(left.id) ?? 0) - (indexById.get(right.id) ?? 0))
        .map((step, rowIndex) => ({
          id: step.id,
          x: 40 + level * 360,
          y: 30 + rowIndex * 130,
          borderColor: STATUS_COLOR_MAP[step.status] ?? "#52525b",
          step
        }));
    });

  return { nodes, edges };
}

function toTaskFlowStep(item: TaskDagNode | TaskSubtask): TaskFlowStep {
  if ("node_id" in item) {
    return {
      id: item.node_id,
      title: item.title,
      assignedAgentId: item.assigned_agent_id ?? null,
      status: normalizeFlowStatus(item.status, item.dispatch_state),
      dependsOn: item.depends_on
    };
  }

  return {
    id: item.step_id,
    title: item.title,
    assignedAgentId: item.assigned_agent_id ?? null,
    status: normalizeFlowStatus(item.status),
    dependsOn: item.depends_on
  };
}

function normalizeFlowStatus(status?: string, dispatchState?: string): string {
  const normalizedDispatch = (dispatchState ?? "").toLowerCase();
  if (normalizedDispatch === "running") {
    return "in_progress";
  }
  if (normalizedDispatch === "completed") {
    return "completed";
  }
  if (normalizedDispatch === "failed") {
    return "failed";
  }

  const normalizedStatus = (status ?? "").toLowerCase();
  if (normalizedStatus === "completed" || normalizedStatus === "failed" || normalizedStatus === "in_progress" || normalizedStatus === "queued") {
    return normalizedStatus;
  }

  return "queued";
}

function getValidDependencies(step: TaskFlowStep, indexById: Map<string, number>): string[] {
  const seen = new Set<string>();
  return step.dependsOn.filter((dependency) => {
    if (dependency === step.id || !indexById.has(dependency) || seen.has(dependency)) {
      return false;
    }
    seen.add(dependency);
    return true;
  });
}
