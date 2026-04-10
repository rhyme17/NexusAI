"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useTasks } from "@/hooks/use-tasks";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";
import { CreateTaskPayload, TaskStatus } from "@/lib/api/types";
import { TaskForm } from "./task-form";
import { TaskList } from "./task-list";

export function TasksPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { isChinese } = useI18n();
  const { tasks, isLoading, error, createTask } = useTasks();
  const initialStatus = searchParams.get("status");
  const [statusFilter, setStatusFilter] = useState<"all" | TaskStatus>(
    initialStatus === "queued" || initialStatus === "in_progress" || initialStatus === "completed" || initialStatus === "failed"
      ? initialStatus
      : "all"
  );
  const [onlyConflicts, setOnlyConflicts] = useState(searchParams.get("conflicts") === "1");

  useEffect(() => {
    const nextStatus = searchParams.get("status");
    const normalizedStatus: "all" | TaskStatus =
      nextStatus === "queued" || nextStatus === "in_progress" || nextStatus === "completed" || nextStatus === "failed"
        ? nextStatus
        : "all";
    const nextConflicts = searchParams.get("conflicts") === "1";
    setStatusFilter((prev) => (prev === normalizedStatus ? prev : normalizedStatus));
    setOnlyConflicts((prev) => (prev === nextConflicts ? prev : nextConflicts));
  }, [searchParams]);

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (statusFilter === "all") {
      params.delete("status");
    } else {
      params.set("status", statusFilter);
    }
    if (onlyConflicts) {
      params.set("conflicts", "1");
    } else {
      params.delete("conflicts");
    }

    const nextQuery = params.toString();
    const currentQuery = searchParams.toString();
    if (nextQuery !== currentQuery) {
      router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
    }
  }, [onlyConflicts, pathname, router, searchParams, statusFilter]);

  const filteredTasks = useMemo(() => {
    return tasks
      .filter((task) => {
        const matchesStatus = statusFilter === "all" || task.status === statusFilter;
        const matchesConflict = !onlyConflicts || Boolean(task.consensus?.conflict_detected);
        return matchesStatus && matchesConflict;
      })
      .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
  }, [onlyConflicts, statusFilter, tasks]);

  async function handleCreate(payload: CreateTaskPayload) {
    const created = await createTask(payload);
    router.push(`/tasks/${created.task_id}`);
  }

  const activeCount = tasks.filter((task) => task.status === "queued" || task.status === "in_progress").length;
  const failedCount = tasks.filter((task) => task.status === "failed").length;

  return (
    <main className="space-y-6 pb-3">
      <header className="nexus-panel relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full bg-[#d97757]/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl space-y-2">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "工作区 / 任务" : "Workspace / Tasks"}</p>
            <h1 className="text-2xl font-semibold text-[#141413] md:text-3xl">
              {isChinese ? "任务工作台" : "Tasks workspace"}
            </h1>
            <p className="text-sm leading-relaxed text-[#6b6860] md:text-base">
              {isChinese
                ? "在这里可以创建任务、筛选任务，并进入任务工作区完成执行与结果查看。"
                : "Create tasks, filter the list, and open a task workspace to run and review results."}
            </p>
          </div>
          <div className="grid min-w-[220px] gap-2 rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-4 text-sm text-[#6b6860]">
            <p>
              <span className="font-medium text-[#141413]">{tasks.length}</span> {isChinese ? "个任务" : "total tasks"}
            </p>
            <p>
              <span className="font-medium text-[#141413]">{activeCount}</span> {isChinese ? "个正在推进" : "actively moving"}
            </p>
            <p>
              <span className="font-medium text-[#141413]">{failedCount}</span> {isChinese ? "个需要关注" : "need failure review"}
            </p>
          </div>
        </div>
      </header>

      {error ? (
        <p className="nexus-panel border-[#dca89f] bg-[#fff1ee] p-3 text-sm text-[#8e3d31]">
          {isChinese ? "任务加载失败" : "Task loading failed"}: {getUserFacingErrorMessage(error, { isChinese, context: "tasks" })}
        </p>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <TaskForm onCreate={handleCreate} />
          <article className="nexus-panel p-4 text-sm text-[#6b6860]">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "使用提示" : "Usage tips"}</p>
            <ul className="mt-3 space-y-2 leading-relaxed">
              <li>• {isChinese ? "创建任务后会自动进入该任务工作区，无需再次查找。" : "After creation, you are routed directly to that task workspace."}</li>
              <li>• {isChinese ? "建议先按状态筛选，再优先处理高优先级任务。" : "Filter by status first, then open the highest-priority item."}</li>
              <li>• {isChinese ? "任务工作区会集中展示执行、事件和结果，减少来回切换。" : "The task workspace centralizes execution, events, and results in one place."}</li>
            </ul>
          </article>
        </div>

        <TaskList
          tasks={filteredTasks}
          totalTaskCount={tasks.length}
          isLoading={isLoading}
          getTaskHref={(task) => `/tasks/${task.task_id}`}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          onlyConflicts={onlyConflicts}
          onOnlyConflictsChange={setOnlyConflicts}
          listMaxHeightClassName="max-h-[70vh]"
        />
      </section>
    </main>
  );
}

