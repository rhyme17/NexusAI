"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { EventInsights } from "@/components/event-insights";
import { EventStream } from "@/components/event-stream";
import { TaskDetail } from "@/components/task-detail";
import { TaskFlow } from "@/components/task-flow";
import { MessageType } from "@/lib/api/types";
import { useAgents } from "@/hooks/use-agents";
import { useTaskEvents } from "@/hooks/use-task-events";
import { useTaskRecord } from "@/hooks/use-task-record";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";
import { useUserKey } from "@/lib/user-key-context";
import { AgentGraph } from "./agent-graph";

export function TaskWorkspace({ taskId }: { taskId: string }) {
  const { isChinese } = useI18n();
  const { userApiKey } = useUserKey();
  const { task, isLoading, error, refresh, updateTask } = useTaskRecord(taskId);
  const { agents, error: agentError, refresh: refreshAgents } = useAgents();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [eventTypes, setEventTypes] = useState<MessageType[]>([]);
  const [eventFrom, setEventFrom] = useState("");
  const [eventTo, setEventTo] = useState("");
  const debouncedEventFrom = useDebouncedValue(eventFrom, 300);
  const debouncedEventTo = useDebouncedValue(eventTo, 300);

  const { events, error: eventError, refresh: refreshEvents, connectionState, insights } = useTaskEvents(taskId, {
    types: eventTypes,
    from: debouncedEventFrom,
    to: debouncedEventTo
  });

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.allSettled([refresh(), refreshAgents(), refreshEvents()]);
    } finally {
      setIsRefreshing(false);
    }
  }, [refresh, refreshAgents, refreshEvents]);

  const taskStateTone = useMemo(() => {
    if (!task) {
      return "border-[#d8d2c4] bg-[#f4efe4] text-[#6b6860]";
    }
    if (task.status === "completed") {
      return "border-[#9bc5a7] bg-[#edf7ef] text-[#2f5d3e]";
    }
    if (task.status === "failed") {
      return "border-[#e6b6ad] bg-[#fff0ed] text-[#c0453a]";
    }
    if (task.status === "in_progress") {
      return "border-[#e5d0b4] bg-[#fff7ec] text-[#9a6a34]";
    }
    return "border-[#d8d2c4] bg-[#f4efe4] text-[#6b6860]";
  }, [task]);

  function toggleEventType(type: MessageType) {
    setEventTypes((prev) => (prev.includes(type) ? prev.filter((item) => item !== type) : [...prev, type]));
  }

  return (
    <main className="space-y-6 pb-3">
      <header className="nexus-panel relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute -right-12 -top-10 h-40 w-40 rounded-full bg-[#3f6b4a]/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl space-y-2">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">
              <Link href="/tasks" className="hover:text-[#c96544]">
                {isChinese ? "任务工作台" : "Tasks"}
              </Link>
              <span className="px-2">/</span>
              <span>{isChinese ? "任务工作区" : "Task workspace"}</span>
            </p>
            <h1 className="text-2xl font-semibold text-[#141413] md:text-3xl">
              {task?.objective ?? (isChinese ? "正在加载任务详情..." : "Loading task...")}
            </h1>
            <p className="text-sm leading-relaxed text-[#6b6860] md:text-base">
              {isChinese
                ? "这里聚焦单个任务，将执行控制、结果、观测与流程统一在同一视图中。"
                : "This page focuses on one task and groups execution, output, observability, and workflow around it."}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {task ? (
              <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-medium capitalize ${taskStateTone}`}>
                {isChinese ? `状态：${task.status}` : `status ${task.status}`}
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => {
                void refreshAll();
              }}
              disabled={isRefreshing}
              className="nexus-button-ghost rounded-full px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              {isRefreshing ? (isChinese ? "刷新中..." : "Refreshing...") : isChinese ? "刷新当前工作区" : "Refresh workspace"}
            </button>
          </div>
        </div>
      </header>

      {error ? (
        <p className="nexus-panel border-[#dca89f] bg-[#fff1ee] p-3 text-sm text-[#8e3d31]">
          {isChinese ? "任务加载失败" : "Task loading failed"}: {getUserFacingErrorMessage(error, { isChinese, context: "task" })}
        </p>
      ) : null}
      {agentError ? (
        <p className="nexus-panel border-[#e6c8ae] bg-[#fff6eb] p-3 text-sm text-[#8a5f33]">
          {isChinese ? "智能体加载失败" : "Agent loading failed"}: {getUserFacingErrorMessage(agentError, { isChinese, context: "agents" })}
        </p>
      ) : null}

      {!task && isLoading ? (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_360px]">
          <div className="nexus-panel min-h-[480px] animate-pulse p-4" />
          <div className="space-y-4">
            <div className="nexus-panel min-h-[180px] animate-pulse p-4" />
            <div className="nexus-panel min-h-[280px] animate-pulse p-4" />
          </div>
        </section>
      ) : null}

      {!task && !isLoading && !error ? (
        <section className="nexus-panel p-6 text-sm text-[#6b6860]">
          {isChinese ? "未找到该任务。请返回任务工作台重新选择。" : "Task not found. Return to the tasks workspace and choose another one."}
        </section>
      ) : null}

      {task ? (
        <>
          <section className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_360px]">
            <TaskDetail task={task} onTaskPatched={updateTask} agents={agents} userApiKey={userApiKey} />
            <div className="space-y-4 xl:sticky xl:top-6 xl:self-start">
              <EventInsights
                latestClaim={insights.latestClaim}
                handoffCount={insights.handoffCount}
                latestDecision={insights.latestDecision}
                latestFailure={insights.latestFailure}
              />
              <TaskFlow task={task} />
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
            <EventStream
              events={events}
              error={eventError ? eventError.message : null}
              connectionState={connectionState}
              selectedTypes={eventTypes}
              from={eventFrom}
              to={eventTo}
              onToggleType={toggleEventType}
              onFromChange={setEventFrom}
              onToChange={setEventTo}
              onRefresh={() => {
                void refreshEvents();
              }}
            />
            <AgentGraph agents={agents} selectedTask={task} />
          </section>
        </>
      ) : null}
    </main>
  );
}

