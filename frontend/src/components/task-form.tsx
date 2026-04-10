"use client";

import { FormEvent, useState } from "react";

import { useI18n } from "@/lib/i18n/language-context";
import { CreateTaskPayload, TaskPriority } from "@/lib/api/types";

interface TaskFormProps {
  onCreate: (payload: CreateTaskPayload) => Promise<void>;
}

interface TaskTemplateOption {
  id: string;
  labelZh: string;
  labelEn: string;
  objectiveZh: string;
  objectiveEn: string;
}

const TASK_TEMPLATES: TaskTemplateOption[] = [
  {
    id: "research_report",
    labelZh: "调研报告",
    labelEn: "Research report",
    objectiveZh:
      "请调研目标主题并输出一份 Markdown 报告，至少包含：背景与范围、核心发现、证据来源、风险与建议、可执行计划。",
    objectiveEn:
      "Research the target topic and output a Markdown report with background/scope, key findings, evidence sources, risks and recommendations, and an executable plan."
  },
  {
    id: "solution_proposal",
    labelZh: "方案草案",
    labelEn: "Solution proposal",
    objectiveZh:
      "请针对该问题提出可落地方案，输出 Markdown 文档，包含目标、约束、候选方案对比、推荐方案、实施步骤与里程碑。",
    objectiveEn:
      "Propose actionable solutions for this problem and output a Markdown document with goals, constraints, option comparison, recommendation, implementation steps, and milestones."
  },
  {
    id: "risk_review",
    labelZh: "风险评估",
    labelEn: "Risk assessment",
    objectiveZh:
      "请对该任务进行风险评估并输出 Markdown 报告，包含风险清单、影响与概率、缓解措施、优先级和监控指标。",
    objectiveEn:
      "Perform a risk assessment and output a Markdown report with risk list, impact and likelihood, mitigation plan, priorities, and monitoring indicators."
  }
];

export function TaskForm({ onCreate }: TaskFormProps) {
  const { isChinese } = useI18n();
  const [objective, setObjective] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("custom");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (objective.trim().length < 3) {
      setError(isChinese ? "任务目标至少需要 3 个字符。" : "Objective must be at least 3 characters.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onCreate({
        objective: objective.trim(),
        priority,
        metadata: {
          output_format: "markdown",
          objective_template: selectedTemplateId === "custom" ? null : selectedTemplateId
        }
      });
      setObjective("");
      setSelectedTemplateId("custom");
      setPriority("medium");
    } catch (err) {
      setError(err instanceof Error ? err.message : isChinese ? "任务创建失败。" : "Task creation failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="nexus-panel space-y-3 p-4 lg:col-span-4 xl:col-span-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{isChinese ? "创建任务" : "Create Task"}</h2>
      <label className="block text-xs text-[#6b6860]">
        {isChinese ? "任务模板" : "Template"}
        <select
          value={selectedTemplateId}
          onChange={(event) => {
            const nextId = event.target.value;
            setSelectedTemplateId(nextId);
            const selected = TASK_TEMPLATES.find((item) => item.id === nextId);
            if (selected) {
              setObjective(isChinese ? selected.objectiveZh : selected.objectiveEn);
              setPriority("high");
            }
          }}
          className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs text-[#141413]"
        >
          <option value="custom">{isChinese ? "自定义" : "Custom"}</option>
          {TASK_TEMPLATES.map((item) => (
            <option key={item.id} value={item.id}>
              {isChinese ? item.labelZh : item.labelEn}
            </option>
          ))}
        </select>
      </label>
      <textarea
        data-testid="task-objective-input"
        value={objective}
        onChange={(event) => setObjective(event.target.value)}
        className="h-28 w-full rounded-xl border border-[#d8d2c4] bg-[#fffdf9] p-3 text-sm text-[#141413] outline-none focus:border-[#d97757]"
        placeholder={isChinese ? "描述你希望 Agent 团队完成的目标" : "Describe what the agents should complete"}
      />
      <div className="flex items-center gap-2">
        <label className="text-xs text-[#6b6860]" htmlFor="priority">
          {isChinese ? "优先级" : "Priority"}
        </label>
        <select
          id="priority"
          value={priority}
          onChange={(event) => setPriority(event.target.value as TaskPriority)}
          className="rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-sm text-[#141413]"
        >
          <option value="low">{isChinese ? "低" : "low"}</option>
          <option value="medium">{isChinese ? "中" : "medium"}</option>
          <option value="high">{isChinese ? "高" : "high"}</option>
        </select>
      </div>
      {error ? <p className="text-xs text-[#c0453a]">{error}</p> : null}
      <button
        data-testid="task-create-button"
        type="submit"
        disabled={isSubmitting}
        className="nexus-button-primary rounded-lg px-3 py-2 text-sm font-medium transition disabled:opacity-40"
      >
        {isSubmitting ? (isChinese ? "提交中..." : "Submitting...") : isChinese ? "创建任务" : "Create"}
      </button>
    </form>
  );
}

