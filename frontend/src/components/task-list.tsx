"use client";

import Link from "next/link";

import { Task, TaskStatus } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/language-context";

type TaskSource = "all" | "human" | "auto_discover";

interface TaskListProps {
  tasks: Task[];
  totalTaskCount?: number;
  isLoading: boolean;
  selectedTaskId?: string | null;
  onSelect?: (task: Task) => void;
  getTaskHref?: (task: Task) => string;
  statusFilter?: "all" | TaskStatus;
  onStatusFilterChange?: (value: "all" | TaskStatus) => void;
  sourceFilter?: TaskSource;
  onSourceFilterChange?: (value: TaskSource) => void;
  onlyConflicts?: boolean;
  onOnlyConflictsChange?: (value: boolean) => void;
  listMaxHeightClassName?: string;
}

export function TaskList({
  tasks,
  totalTaskCount,
  isLoading,
  selectedTaskId = null,
  onSelect,
  getTaskHref,
  statusFilter = "all",
  onStatusFilterChange,
  sourceFilter = "all",
  onSourceFilterChange,
  onlyConflicts = false,
  onOnlyConflictsChange,
  listMaxHeightClassName
}: TaskListProps) {
  const { isChinese, text } = useI18n();
  const total = totalTaskCount ?? tasks.length;

  return (
    <section className="nexus-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{text.sectionTasks}</h2>
        <span className="text-xs text-[#6b6860]">
          {isChinese ? `${tasks.length} 条已展示 / 共 ${total} 条` : `${tasks.length} shown / ${total} total`}
        </span>
      </div>

      <div className="mb-3 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
        <label className="text-xs text-[#6b6860]">
          {isChinese ? "状态筛选" : "Status Filter"}
          <select
            data-testid="task-status-filter"
            value={statusFilter}
            onChange={(event) => onStatusFilterChange?.(event.target.value as "all" | TaskStatus)}
            className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs text-[#141413]"
          >
            <option value="all">{isChinese ? "全部" : "all"}</option>
            <option value="queued">{isChinese ? "排队中" : "queued"}</option>
            <option value="in_progress">{isChinese ? "执行中" : "in_progress"}</option>
            <option value="completed">{isChinese ? "已完成" : "completed"}</option>
            <option value="failed">{isChinese ? "失败" : "failed"}</option>
          </select>
        </label>

        <label className="text-xs text-[#6b6860]">
          {isChinese ? "来源筛选" : "Source Filter"}
          <select
            data-testid="task-source-filter"
            value={sourceFilter}
            onChange={(event) => onSourceFilterChange?.(event.target.value as TaskSource)}
            className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs text-[#141413]"
          >
            <option value="all">{isChinese ? "全部来源" : "all sources"}</option>
            <option value="human">{isChinese ? "人工输入" : "human input"}</option>
            <option value="auto_discover">{isChinese ? "自动发现" : "auto discover"}</option>
          </select>
        </label>

        <label className="flex items-center gap-2 self-end text-xs text-[#3e3a35]">
          <input
            data-testid="task-only-conflicts-toggle"
            type="checkbox"
            checked={onlyConflicts}
            onChange={(event) => onOnlyConflictsChange?.(event.target.checked)}
            className="rounded border-[#c7c0b1] bg-[#fffdf9]"
          />
          {isChinese ? "仅冲突" : "conflicts only"}
        </label>
      </div>

      {isLoading ? (
        <div className="space-y-2" aria-busy="true" aria-live="polite">
          <p className="text-sm text-[#6b6860]">{isChinese ? "任务加载中..." : "Loading tasks..."}</p>
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={`task-skeleton-${index}`} className="rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-3 animate-pulse">
              <div className="h-4 w-3/4 rounded bg-[#ece6d9]" />
              <div className="mt-2 h-3 w-1/2 rounded bg-[#f2ece1]" />
              <div className="mt-2 h-3 w-2/3 rounded bg-[#f2ece1]" />
            </div>
          ))}
        </div>
      ) : null}
      {!isLoading && tasks.length === 0 ? <p className="text-sm text-[#6b6860]">{isChinese ? "暂无任务。" : "No tasks yet."}</p> : null}
      <ul className={`space-y-2 overflow-auto pr-1 ${listMaxHeightClassName ?? ""}`}>
        {tasks.map((task) => {
          const isSelected = task.task_id === selectedTaskId;
          const rowClassName = `block w-full rounded-2xl border px-3 py-3 text-left text-sm transition ${
            isSelected
              ? "border-[#d97757] bg-[#fff5f1]"
              : "border-[#ddd7ca] bg-[#fffcf6] hover:border-[#c7c0b1] hover:bg-[#fff8ef]"
          }`;

          const taskSource = task.metadata?.source || "human";
          const sourceLabel = taskSource === "auto_discover" 
            ? (isChinese ? "🤖 自动发现" : "🤖 auto")
            : (isChinese ? "👤 人工" : "👤 human");

          const rowContent = (
            <>
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium leading-relaxed text-[#141413]">{task.objective}</p>
                <div className="flex shrink-0 gap-1">
                  <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${getStatusTone(task.status)}`}>
                    {task.status}
                  </span>
                </div>
              </div>
              <p className="mt-2 text-xs text-[#6b6860]">
                {task.task_id} • {isChinese ? "进度" : "progress"} {task.progress}%
              </p>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-[#8a867d]">
                <span>{isChinese ? "优先级" : "priority"}: {task.priority}</span>
                <span>{isChinese ? "持有者" : "owner"}: {task.current_agent_id ?? (isChinese ? "未认领" : "unclaimed")}</span>
                <span className="rounded-full border border-[#d8d2c4] bg-[#f4efe4] px-2 py-0.5">
                  {sourceLabel}
                </span>
                {task.consensus?.conflict_detected ? (
                  <span className="rounded-full border border-[#e5d0b4] bg-[#fff7ec] px-2 py-0.5 text-[#9a6a34]">
                    {isChinese ? "存在冲突" : "conflict"}
                  </span>
                ) : null}
              </div>
            </>
          );

          return (
            <li key={task.task_id}>
              {getTaskHref ? (
                <Link data-testid={`task-item-${task.task_id}`} href={getTaskHref(task)} className={rowClassName}>
                  {rowContent}
                </Link>
              ) : (
                <button
                  data-testid={`task-item-${task.task_id}`}
                  type="button"
                  onClick={() => onSelect?.(task)}
                  className={rowClassName}
                >
                  {rowContent}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function getStatusTone(status: TaskStatus) {
  if (status === "completed") {
    return "border border-[#9bc5a7] bg-[#edf7ef] text-[#2f5d3e]";
  }
  if (status === "failed") {
    return "border border-[#e6b6ad] bg-[#fff0ed] text-[#c0453a]";
  }
  if (status === "in_progress") {
    return "border border-[#e5d0b4] bg-[#fff7ec] text-[#9a6a34]";
  }
  return "border border-[#d8d2c4] bg-[#f4efe4] text-[#6b6860]";
}

