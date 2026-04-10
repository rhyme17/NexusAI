"use client";

import { useMemo, useState } from "react";

import ReactFlow, {
  Background,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  Position
} from "reactflow";
import "reactflow/dist/style.css";

import { Task } from "@/lib/api/types";
import { getTaskDecomposition } from "@/components/task-detail-helpers";
import { buildTaskFlowLayout, buildTaskFlowSteps } from "@/components/task-flow-helpers";
import { useI18n } from "@/lib/i18n/language-context";

interface TaskFlowProps {
  task: Task | null;
}

export function TaskFlow({ task }: TaskFlowProps) {
  const { isChinese, text } = useI18n();
  const [showMiniMap, setShowMiniMap] = useState(false);
  const decomposition = useMemo(() => getTaskDecomposition(task), [task]);

  const graph = useMemo(() => {
    if (!decomposition) {
      return { nodes: [] as Node[], edges: [] as Edge[] };
    }

    const layout = buildTaskFlowLayout(buildTaskFlowSteps(decomposition));

    const nodes: Node[] = layout.nodes.map((item) => ({
      id: item.id,
      data: {
        label: (
          <div className="space-y-1 text-left">
            <p className="text-xs font-semibold text-[#141413]">{item.step.title}</p>
            <p className="text-[10px] text-[#8a867d]">{item.step.id}</p>
            <p className="text-[10px] text-[#8a867d]">
              {isChinese ? "分配给" : "assigned"}: {item.step.assignedAgentId ?? (isChinese ? "未分配" : "unassigned")}
            </p>
            <p className="text-[10px] uppercase text-[#6b6860]">{item.step.status}</p>
          </div>
        )
      },
      position: { x: item.x, y: item.y },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      draggable: false,
      style: {
        width: 320,
        borderRadius: 10,
        border: `1px solid ${item.borderColor}`,
        background: "#fffaf2",
        color: "#141413"
      }
    }));

    const edges: Edge[] = layout.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: edge.animated,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 18,
        height: 18,
        color: "#c3bba8"
      },
      style: {
        stroke: "#c3bba8"
      }
    }));

    return { nodes, edges };
  }, [decomposition, isChinese]);

  return (
    <section className="nexus-panel p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{text.sectionTaskFlow}</h3>
      {!task ? <p className="text-sm text-[#6b6860]">{isChinese ? "请选择任务查看分解流程。" : "Select a task to inspect decomposition."}</p> : null}
      {task && (!decomposition?.subtasks || decomposition.subtasks.length === 0) ? (
        <p className="text-sm text-[#6b6860]">{isChinese ? "未找到任务分解元数据。" : "No decomposition metadata found."}</p>
      ) : null}
      {decomposition ? (
        <div className="h-[460px] rounded-xl border border-[#ddd7ca] bg-[#fffdf9]">
          <div className="flex justify-end px-2 pt-2">
            <button
              type="button"
              onClick={() => setShowMiniMap((prev) => !prev)}
              className="rounded-lg border border-[#d8d2c4] bg-[#f4efe4] px-2 py-1 text-[11px] text-[#6b6860]"
            >
              {showMiniMap ? (isChinese ? "隐藏迷你地图" : "Hide minimap") : (isChinese ? "显示迷你地图" : "Show minimap")}
            </button>
          </div>
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            fitView
            fitViewOptions={{ padding: 0.25 }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            zoomOnScroll
            panOnScroll
            minZoom={0.5}
            maxZoom={1.6}
          >
            <Background color="#e4decd" gap={20} />
            <Controls position="bottom-right" />
            {showMiniMap ? (
              <MiniMap
                nodeColor="#d3ccba"
                nodeBorderRadius={4}
                maskColor="rgba(20, 20, 19, 0.08)"
                pannable
                zoomable
                position="top-right"
                style={{ width: 120, height: 80, border: "1px solid #ddd7ca", borderRadius: 8, background: "#fffcf6" }}
              />
            ) : null}
          </ReactFlow>
        </div>
      ) : null}
    </section>
  );
}

