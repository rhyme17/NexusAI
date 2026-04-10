import { Agent, Task } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/language-context";

interface SystemOverviewProps {
  tasks: Task[];
  agents: Agent[];
  selectedTask: Task | null;
  backendStatus: "checking" | "online" | "offline";
  backendReadOnly: boolean;
  storageBackend: string | null;
  onRefresh: () => void;
  isRefreshing: boolean;
}

function getStatusTone(status: "checking" | "online" | "offline"): string {
  if (status === "online") {
    return "border-[#9bc5a7] bg-[#edf7ef] text-[#3f6b4a]";
  }
  if (status === "offline") {
    return "border-[#e6b6ad] bg-[#fff0ed] text-[#c0453a]";
  }
  return "border-[#e5d0b4] bg-[#fff7ec] text-[#9a6a34]";
}

export function SystemOverview({
  tasks,
  agents,
  selectedTask,
  backendStatus,
  backendReadOnly,
  storageBackend,
  onRefresh,
  isRefreshing
}: SystemOverviewProps) {
  const { isChinese, text } = useI18n();
  const activeCount = tasks.filter((task) => task.status === "queued" || task.status === "in_progress").length;
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const failedCount = tasks.filter((task) => task.status === "failed").length;
  const busyAgents = agents.filter((agent) => agent.status === "busy").length;

  const cards = [
    {
      kind: "backend",
      label: isChinese ? "后端" : "Backend",
      value:
        backendStatus === "online"
          ? text.healthOnline
          : backendStatus === "offline"
            ? text.healthOffline
            : text.healthChecking,
      subtext:
        backendStatus === "online"
          ? isChinese
            ? `FastAPI 服务可达${backendReadOnly ? "（当前只读维护）" : ""}${storageBackend ? ` • backend=${storageBackend}` : ""}`
            : `FastAPI reachable${backendReadOnly ? " (read-only maintenance)" : ""}${storageBackend ? ` • backend=${storageBackend}` : ""}`
          : isChinese
            ? "请检查后端服务进程"
            : "Check local backend process"
    },
    {
      kind: "tasks",
      label: isChinese ? "任务" : "Tasks",
      value: String(tasks.length),
      subtext: isChinese
        ? `${activeCount} 进行中 / ${completedCount} 已完成 / ${failedCount} 失败`
        : `${activeCount} active / ${completedCount} completed / ${failedCount} failed`
    },
    {
      kind: "agents",
      label: isChinese ? "智能体" : "Agents",
      value: String(agents.length),
      subtext: isChinese
        ? `${busyAgents} 忙碌 / ${Math.max(agents.length - busyAgents, 0)} 就绪`
        : `${busyAgents} busy / ${Math.max(agents.length - busyAgents, 0)} ready`
    },
    {
      kind: "selected",
      label: isChinese ? "当前选中" : "Selected",
      value: selectedTask?.status ?? (isChinese ? "无" : "none"),
      subtext: selectedTask ? selectedTask.task_id : isChinese ? "请选择一个任务查看" : "Choose a task to inspect"
    }
  ];

  return (
    <section className="nexus-panel p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{text.sectionSystemOverview}</h2>
          <p className="mt-1 text-xs text-[#6b6860]">
            {isChinese ? "从任务、Agent 与连接状态快速判断系统运行质量。" : "Quickly scan task flow, agent readiness, and backend health."}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="nexus-button-ghost rounded-lg px-3 py-1.5 text-xs transition disabled:opacity-50"
        >
          {isRefreshing ? text.refreshing : text.refreshAll}
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-sm">
            <p className="text-xs uppercase tracking-wide text-[#8a867d]">{card.label}</p>
            <p
              className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-medium capitalize ${
                card.kind === "backend" ? getStatusTone(backendStatus) : "border-[#ddd7ca] bg-[#f4efe4] text-[#3e3a35]"
              }`}
            >
              {card.value}
            </p>
            <p className="mt-2 text-xs text-[#6b6860]">{card.subtext}</p>
          </div>
        ))}
      </div>
    </section>
  );
}


