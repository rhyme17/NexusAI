"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { useAgents } from "@/hooks/use-agents";
import { useBackendHealth } from "@/hooks/use-backend-health";
import { useTasks } from "@/hooks/use-tasks";
import { useI18n } from "@/lib/i18n/language-context";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { Task } from "@/lib/api/types";
import { SystemOverview } from "./system-overview";

export function Dashboard() {
  const { text } = useI18n();
  const { isChinese } = useI18n();
  const { tasks, isLoading, error, refresh } = useTasks();
  const { agents, error: agentError, refresh: refreshAgents } = useAgents();
  const { status: backendStatus, readOnly: backendReadOnly, storageBackend, refresh: refreshHealth } = useBackendHealth();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const orderedTasks = useMemo(
    () => [...tasks].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at)),
    [tasks]
  );

  const spotlightTask = useMemo(
    () => orderedTasks.find((task) => task.status === "in_progress") ?? orderedTasks.find((task) => task.status === "queued") ?? orderedTasks[0] ?? null,
    [orderedTasks]
  );

  const recentTasks = orderedTasks.slice(0, 5);

  const roleSummary = useMemo(() => {
    const summary = new Map<string, number>();
    agents.forEach((agent) => {
      summary.set(agent.role, (summary.get(agent.role) ?? 0) + 1);
    });
    return Array.from(summary.entries()).sort((left, right) => right[1] - left[1]);
  }, [agents]);

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.allSettled([refresh(), refreshAgents(), refreshHealth()]);
    } finally {
      setIsRefreshing(false);
    }
  }, [refresh, refreshAgents, refreshHealth]);

  return (
    <main className="space-y-6 pb-3">

      {error ? (
        <p className="nexus-panel border-[#dca89f] bg-[#fff1ee] p-3 text-sm text-[#8e3d31]">
          {text.backendErrorPrefix}: {getUserFacingErrorMessage(error, { isChinese, context: "backend" })}
        </p>
      ) : null}
      {agentError ? (
        <p className="nexus-panel border-[#e6c8ae] bg-[#fff6eb] p-3 text-sm text-[#8a5f33]">
          {text.agentErrorPrefix}: {getUserFacingErrorMessage(agentError, { isChinese, context: "agents" })}
        </p>
      ) : null}
      {backendReadOnly ? (
        <p className="nexus-panel border-[#e5d0b4] bg-[#fff7ec] p-3 text-sm text-[#9a6a34]">
          {isChinese
            ? `系统当前处于只读维护模式，写入操作已冻结${storageBackend ? `（backend=${storageBackend}）` : ""}。`
            : `The system is currently in read-only maintenance mode; write operations are frozen${storageBackend ? ` (backend=${storageBackend})` : ""}.`}
        </p>
      ) : null}

      <SystemOverview
        tasks={tasks}
        agents={agents}
        selectedTask={spotlightTask}
        backendStatus={backendStatus}
        backendReadOnly={backendReadOnly}
        storageBackend={storageBackend}
        onRefresh={() => {
          void refreshAll();
        }}
        isRefreshing={isRefreshing}
      />

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_420px]">
        <article className="nexus-panel p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "当前焦点" : "Current focus"}</p>
              <h2 className="mt-1 text-xl font-semibold text-[#141413]">
                {spotlightTask?.objective ?? (isChinese ? "还没有任务，可以先创建一个任务。" : "No tasks yet - create your first task.")}
              </h2>
            </div>
            {spotlightTask ? <StatusBadge task={spotlightTask} isChinese={isChinese} compact /> : null}
          </div>

          {spotlightTask ? (
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <SpotlightCard
                label={isChinese ? "当前持有者" : "Current owner"}
                value={spotlightTask.current_agent_id ?? (isChinese ? "未认领" : "unclaimed")}
                note={isChinese ? "谁正在推进这个任务" : "Who is actively driving the task"}
              />
              <SpotlightCard
                label={isChinese ? "进度" : "Progress"}
                value={`${spotlightTask.progress}%`}
                note={isChinese ? "便于快速判断是否接近完成" : "Useful for deciding if the task is close to completion"}
              />
              <SpotlightCard
                label={isChinese ? "建议下一步" : "Suggested next step"}
                value={getNextStepLabel(spotlightTask, isChinese)}
                note={isChinese ? "基于当前状态给出最自然的后续动作" : "The most natural action based on current state"}
              />
            </div>
          ) : null}

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "推荐操作" : "Recommended action"}</p>
              <p className="mt-2 text-sm leading-relaxed text-[#6b6860]">
                {spotlightTask
                  ? isChinese
                    ? "直接进入任务工作区查看执行、失败记录、事件流和流程图，不再把所有信息一次性堆在首页。"
                    : "Jump into the task workspace for execution, retries, events, and flow instead of stacking everything on the landing page."
                  : isChinese
                    ? "前往任务台创建一个目标，例如“调研某项技术并产出执行方案”，然后在任务工作区持续推进。"
                    : "Create a task like \"research a topic and draft an execution plan\", then continue in the task workspace."}
              </p>
            </div>
            <div className="rounded-2xl border border-[#ddd7ca] bg-[#fff8ef] p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "推荐顺序" : "Suggested flow"}</p>
              <ol className="mt-2 space-y-2 text-sm leading-relaxed text-[#6b6860]">
                <li>1. {isChinese ? "在任务台创建任务" : "Create a task in Tasks"}</li>
                <li>2. {isChinese ? "进入任务工作区执行并查看结果" : "Open the task workspace to run and review results"}</li>
                <li>3. {isChinese ? "在智能体页查看协作分工和状态" : "Use Agents to inspect collaboration roles and status"}</li>
              </ol>
            </div>
          </div>
        </article>

        <article className="nexus-panel p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "最近任务" : "Recent tasks"}</p>
              <h2 className="mt-1 text-lg font-semibold text-[#141413]">
                {isChinese ? "只展示最近变化，避免首页过载" : "Only the latest changes, not the entire backlog"}
              </h2>
            </div>
            <Link href="/tasks" className="text-sm font-medium text-[#c96544] hover:text-[#b95535]">
              {isChinese ? "查看全部 →" : "View all →"}
            </Link>
          </div>

          <div className="mt-4 space-y-3">
            {isLoading ? <p className="text-sm text-[#6b6860]">{isChinese ? "任务加载中..." : "Loading tasks..."}</p> : null}
            {!isLoading && recentTasks.length === 0 ? (
              <p className="text-sm text-[#6b6860]">{isChinese ? "暂无任务，进入任务台即可开始。" : "No tasks yet. Head to Tasks to start."}</p>
            ) : null}
            {recentTasks.map((task) => (
              <Link
                key={task.task_id}
                href={`/tasks/${task.task_id}`}
                className="block rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-4 transition hover:border-[#c8bfaf] hover:bg-[#fff8ef]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-[#141413]">{task.objective}</p>
                    <p className="mt-1 text-xs text-[#6b6860]">
                      {task.task_id} • {isChinese ? "更新于" : "updated"} {formatTimestamp(task.updated_at)}
                    </p>
                  </div>
                  <StatusBadge task={task} isChinese={isChinese} compact />
                </div>
              </Link>
            ))}
          </div>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-2 pb-2">
        <article className="nexus-panel p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "智能体快照" : "Agent snapshot"}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <SpotlightCard
              label={isChinese ? "在线智能体" : "Online agents"}
              value={String(agents.filter((agent) => agent.status !== "offline").length)}
              note={isChinese ? "可以立即参与任务的智能体" : "Agents immediately available for work"}
            />
            <SpotlightCard
              label={isChinese ? "忙碌智能体" : "Busy agents"}
              value={String(agents.filter((agent) => agent.status === "busy").length)}
              note={isChinese ? "适合展示调度负载" : "Useful for explaining workload distribution"}
            />
          </div>

          <div className="mt-4 space-y-2">
            {agents.length === 0 ? <p className="text-sm text-[#6b6860]">{isChinese ? "暂无智能体数据。" : "No agent data yet."}</p> : null}
            {roleSummary.map(([role, count]) => (
              <div key={role} className="flex items-center justify-between rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] px-3 py-2 text-sm">
                <span className="text-[#3e3a35]">{role}</span>
                <span className="rounded-full bg-[#f2ece1] px-2 py-1 text-xs text-[#6b6860]">{count}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="nexus-panel p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "常用入口" : "Quick access"}</p>
          <div className="mt-4 space-y-3 text-sm leading-relaxed text-[#6b6860]">
            <p>
              {isChinese
                ? "如果你要创建或推进任务，请先进入任务台；如果你要了解当前协作关系和负载，请进入智能体页。"
                : "Go to Tasks to create or continue work, and go to Agents to understand collaboration and workload."}
            </p>
            <p>
              {isChinese
                ? "设置页可统一管理账号安全、模型密钥、Agent 配置和管理员功能。"
                : "Use Settings to manage account security, model keys, agent configuration, and admin controls."}
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/tasks" className="inline-flex text-sm font-medium text-[#c96544] hover:text-[#b95535]">
                {isChinese ? "前往任务台 →" : "Open tasks →"}
              </Link>
              <Link href="/agents" className="inline-flex text-sm font-medium text-[#c96544] hover:text-[#b95535]">
                {isChinese ? "前往智能体页 →" : "Open agents →"}
              </Link>
              <Link href="/settings" className="inline-flex text-sm font-medium text-[#c96544] hover:text-[#b95535]">
                {isChinese ? "前往设置页 →" : "Open settings →"}
              </Link>
            </div>
          </div>
        </article>
      </section>
    </main>
  );
}

function SpotlightCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{label}</p>
      <p className="mt-2 text-lg font-semibold text-[#141413]">{value}</p>
      <p className="mt-2 text-xs leading-relaxed text-[#6b6860]">{note}</p>
    </div>
  );
}

function StatusBadge({ task, isChinese, compact = false }: { task: Task; isChinese: boolean; compact?: boolean }) {
  const tone =
    task.status === "completed"
      ? "border-[#9bc5a7] bg-[#edf7ef] text-[#2f5d3e]"
      : task.status === "failed"
        ? "border-[#e6b6ad] bg-[#fff0ed] text-[#c0453a]"
        : task.status === "in_progress"
          ? "border-[#e5d0b4] bg-[#fff7ec] text-[#9a6a34]"
          : "border-[#d8d2c4] bg-[#f4efe4] text-[#6b6860]";

  return (
    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium capitalize ${tone}`}>
      {compact ? task.status : `${isChinese ? "状态" : "Status"}: ${task.status}`}
    </span>
  );
}

function getNextStepLabel(task: Task, isChinese: boolean) {
  if (task.status === "failed") {
    return isChinese ? "检查失败原因并重试" : "Inspect failure and retry";
  }
  if (task.status === "completed") {
    return isChinese ? "查看结果与共识" : "Review output and consensus";
  }
  return isChinese ? "进入工作区继续推进" : "Open workspace and continue";
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

