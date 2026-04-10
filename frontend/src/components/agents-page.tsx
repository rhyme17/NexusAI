"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useAgents } from "@/hooks/use-agents";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useTasks } from "@/hooks/use-tasks";
import { apiClient } from "@/lib/api/client";
import { getAgentDisplayName } from "@/lib/agents/display-name";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";
import { AgentGraph } from "./agent-graph";
import { RoleRadarChart } from "./role-radar-chart";

export function AgentsPage() {
  const { isChinese } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status");
  const [agentSkillFilter, setAgentSkillFilter] = useState(searchParams.get("skill") ?? "");
  const [agentStatusFilter, setAgentStatusFilter] = useState<"all" | "online" | "offline" | "busy">(
    initialStatus === "online" || initialStatus === "offline" || initialStatus === "busy" ? initialStatus : "all"
  );
  const debouncedAgentSkillFilter = useDebouncedValue(agentSkillFilter, 250);
  const isSkillFilterPending = agentSkillFilter.trim() !== debouncedAgentSkillFilter.trim();
  const { agents: sourceAgents, error, isLoading, refresh } = useAgents({
    status: agentStatusFilter === "all" ? undefined : agentStatusFilter
  });
  const { tasks } = useTasks();
  const [statusDrafts, setStatusDrafts] = useState<Record<string, "online" | "offline" | "busy">>({});
  const [statusBusyAgentId, setStatusBusyAgentId] = useState<string | null>(null);
  const [statusActionError, setStatusActionError] = useState<string | null>(null);
  const [statusPanelFilter, setStatusPanelFilter] = useState<"all" | "online" | "offline" | "busy">("all");
  const [statusPanelKeyword, setStatusPanelKeyword] = useState("");
  const [roleViewMode, setRoleViewMode] = useState<"list" | "radar">("list");

  function getDraftStatus(agentId: string, currentStatus: "online" | "offline" | "busy") {
    return statusDrafts[agentId] ?? currentStatus;
  }

  async function onUpdateAgentStatus(agentId: string, status: "online" | "offline" | "busy") {
    setStatusBusyAgentId(agentId);
    setStatusActionError(null);
    try {
      await apiClient.updateAgentStatus(agentId, status);
      await refresh();
    } catch (err) {
      setStatusActionError(
        getUserFacingErrorMessage(err, {
          isChinese,
          context: "agents",
          fallback: isChinese ? "更新 Agent 状态失败。" : "Failed to update agent status."
        })
      );
    } finally {
      setStatusBusyAgentId(null);
    }
  }

  const agents = useMemo(() => {
    const query = debouncedAgentSkillFilter.trim();
    if (!query) {
      return sourceAgents;
    }
    return sourceAgents.filter((agent) => matchesAgentQuery(agent, query));
  }, [debouncedAgentSkillFilter, sourceAgents]);

  useEffect(() => {
    const nextSkill = searchParams.get("skill") ?? "";
    const nextStatusRaw = searchParams.get("status");
    const nextStatus: "all" | "online" | "offline" | "busy" =
      nextStatusRaw === "online" || nextStatusRaw === "offline" || nextStatusRaw === "busy"
        ? nextStatusRaw
        : "all";
    setAgentSkillFilter((prev) => (prev === nextSkill ? prev : nextSkill));
    setAgentStatusFilter((prev) => (prev === nextStatus ? prev : nextStatus));
  }, [searchParams]);

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString());
    const skill = debouncedAgentSkillFilter.trim();
    if (skill) {
      params.set("skill", skill);
    } else {
      params.delete("skill");
    }

    if (agentStatusFilter === "all") {
      params.delete("status");
    } else {
      params.set("status", agentStatusFilter);
    }

    const nextQuery = params.toString();
    const currentQuery = searchParams.toString();
    if (nextQuery !== currentQuery) {
      router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
    }
  }, [debouncedAgentSkillFilter, agentStatusFilter, pathname, router, searchParams]);

  const focusTask = useMemo(
    () => tasks.find((task) => task.status === "in_progress") ?? tasks.find((task) => task.status === "queued") ?? tasks[0] ?? null,
    [tasks]
  );

  const roleSummary = useMemo(() => {
    const summary = new Map<string, number>();
    agents.forEach((agent) => {
      summary.set(agent.role, (summary.get(agent.role) ?? 0) + 1);
    });
    return Array.from(summary.entries()).sort((left, right) => right[1] - left[1]);
  }, [agents]);

  const allSkills = useMemo(() => {
    return Array.from(new Set(agents.flatMap((agent) => agent.skills))).sort((left, right) => left.localeCompare(right));
  }, [agents]);

  const statusManagedAgents = useMemo(() => {
    const keyword = statusPanelKeyword.trim().toLowerCase();
    return agents.filter((agent) => {
      if (statusPanelFilter !== "all" && agent.status !== statusPanelFilter) {
        return false;
      }
      if (!keyword) {
        return true;
      }
      return (
        agent.agent_id.toLowerCase().includes(keyword)
        || agent.role.toLowerCase().includes(keyword)
        || agent.name.toLowerCase().includes(keyword)
      );
    });
  }, [agents, statusPanelFilter, statusPanelKeyword]);

  return (
    <main className="space-y-6 pb-3">
      <header className="nexus-panel relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute -right-12 -top-10 h-40 w-40 rounded-full bg-[#d97757]/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl space-y-2">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">Workspace / Agents</p>
            <h1 className="text-2xl font-semibold text-[#141413] md:text-3xl">
              {isChinese ? "智能体视图" : "Agents view"}
            </h1>
            <p className="text-sm leading-relaxed text-[#6b6860] md:text-base">
              {isChinese
                ? "把角色网络与技能分布单独放出来，用户理解协作关系时就不必和任务细节争夺注意力。"
                : "Give roles, readiness, and skills their own space so the collaboration story does not compete with task detail."}
            </p>
          </div>
          <div className="grid min-w-[220px] gap-2 rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-4 text-sm text-[#6b6860]">
            <p>
              <span className="font-medium text-[#141413]">{agents.length}</span> {isChinese ? "个智能体" : "agents"}
            </p>
            <p>
              <span className="font-medium text-[#141413]">{agents.filter((agent) => agent.status === "busy").length}</span> {isChinese ? "个忙碌" : "busy"}
            </p>
            <p>
              <span className="font-medium text-[#141413]">{allSkills.length}</span> {isChinese ? "种技能标签" : "distinct skills"}
            </p>
          </div>
        </div>
      </header>

      {error ? (
        <p className="nexus-panel border-[#e6c8ae] bg-[#fff6eb] p-3 text-sm text-[#8a5f33]">
          {isChinese ? "智能体加载失败" : "Agent loading failed"}: {getUserFacingErrorMessage(error, { isChinese, context: "agents" })}
        </p>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <AgentGraph agents={agents} selectedTask={focusTask} />
        <div className="space-y-4">
          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "发现 Agent" : "Discover agents"}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {DISCOVER_QUICK_CHIPS.map((chip) => (
                <button
                  key={chip.keyword}
                  type="button"
                  onClick={() => setAgentSkillFilter(chip.keyword)}
                  className="rounded-full border border-[#d8d2c4] bg-[#f5f1e7] px-2 py-1 text-xs text-[#6b6860] hover:bg-[#ece7da]"
                >
                  {isChinese ? chip.labelZh : chip.labelEn}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setAgentSkillFilter("")}
                className="rounded-full border border-[#d8d2c4] bg-[#fffcf6] px-2 py-1 text-xs text-[#8a867d]"
              >
                {isChinese ? "清空" : "Clear"}
              </button>
            </div>
            <div className="mt-3 grid gap-2">
              <input
                data-testid="agent-filter-skill-input"
                value={agentSkillFilter}
                onChange={(event) => setAgentSkillFilter(event.target.value)}
                placeholder={isChinese ? "按技能/角色搜索（支持中文，例如：规划、写作、评审）" : "Filter by skill or role (e.g. review)"}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
              />
              <select
                data-testid="agent-filter-status-select"
                value={agentStatusFilter}
                onChange={(event) => setAgentStatusFilter(event.target.value as "all" | "online" | "offline" | "busy")}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
              >
                <option value="all">{isChinese ? "全部状态" : "All statuses"}</option>
                <option value="online">online</option>
                <option value="busy">busy</option>
                <option value="offline">offline</option>
              </select>
            </div>
            <p className="mt-2 text-xs text-[#8a867d]">
              {isChinese
                ? "支持中文关键词检索（例如：规划/研究/写作/评审/仲裁），自动匹配常用英文技能标签。"
                : "Chinese keyword search is supported and mapped to common English skill labels."}
            </p>
            {isSkillFilterPending ? (
              <p className="mt-1 text-[11px] text-[#9a6a34]" aria-live="polite">
                {isChinese ? "正在应用筛选..." : "Applying filter..."}
              </p>
            ) : null}
          </article>

          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "更多配置" : "More configuration"}</p>
            <p className="mt-3 text-sm leading-relaxed text-[#6b6860]">
              {isChinese
                ? "注册 Agent、调整账号权限与系统管理入口都在设置页。"
                : "Agent registration, account permissions, and system administration are available in Settings."}
            </p>
            <Link href="/settings" className="mt-3 inline-flex text-sm font-medium text-[#c96544] hover:text-[#b95535]">
              {isChinese ? "前往设置页 →" : "Open settings →"}
            </Link>
          </article>

          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "角色分布" : "Role distribution"}</p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => setRoleViewMode("list")}
                className={`rounded-lg px-2 py-1 text-xs ${
                  roleViewMode === "list" ? "bg-[#141413] text-[#f5f3ec]" : "bg-[#f4efe4] text-[#6b6860]"
                }`}
              >
                {isChinese ? "原模式" : "List"}
              </button>
              <button
                type="button"
                onClick={() => setRoleViewMode("radar")}
                className={`rounded-lg px-2 py-1 text-xs ${
                  roleViewMode === "radar" ? "bg-[#141413] text-[#f5f3ec]" : "bg-[#f4efe4] text-[#6b6860]"
                }`}
              >
                {isChinese ? "雷达图" : "Radar"}
              </button>
            </div>
            <div className="mt-3 space-y-2">
              {isLoading ? (
                <div className="space-y-2" aria-busy="true" aria-live="polite">
                  <p className="text-sm text-[#6b6860]">{isChinese ? "智能体加载中..." : "Loading agents..."}</p>
                  {Array.from({ length: 3 }).map((_, index) => (
                    <div key={`role-skeleton-${index}`} className="h-9 rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] animate-pulse" />
                  ))}
                </div>
              ) : null}
              {!isLoading && roleSummary.length === 0 ? <p className="text-sm text-[#6b6860]">{isChinese ? "暂无角色数据。" : "No role data yet."}</p> : null}
              {roleViewMode === "list"
                ? roleSummary.map(([role, count]) => (
                    <div key={role} className="flex items-center justify-between rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] px-3 py-2 text-sm">
                      <span className="text-[#3e3a35]">{role}</span>
                      <span className="rounded-full bg-[#f2ece1] px-2 py-1 text-xs text-[#6b6860]">{count}</span>
                    </div>
                  ))
                : <RoleRadarChart items={roleSummary} isChinese={isChinese} />}
            </div>
          </article>

          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "在线状态管理" : "Status management"}</p>
            <div className="mt-3 grid gap-2">
              <input
                value={statusPanelKeyword}
                onChange={(event) => setStatusPanelKeyword(event.target.value)}
                placeholder={isChinese ? "按名称/角色/ID 过滤" : "Filter by name/role/id"}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
              />
              <select
                value={statusPanelFilter}
                onChange={(event) => setStatusPanelFilter(event.target.value as "all" | "online" | "offline" | "busy")}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
              >
                <option value="all">{isChinese ? "全部状态" : "All statuses"}</option>
                <option value="online">online</option>
                <option value="busy">busy</option>
                <option value="offline">offline</option>
              </select>
            </div>
            <div className="mt-3 max-h-[360px] space-y-2 overflow-y-auto pr-1">
              {isLoading
                ? Array.from({ length: 3 }).map((_, index) => (
                    <div key={`status-skeleton-${index}`} className="rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-3 animate-pulse">
                      <div className="h-4 w-1/2 rounded bg-[#ece6d9]" />
                      <div className="mt-2 h-3 w-2/3 rounded bg-[#f2ece1]" />
                    </div>
                  ))
                : null}
              {statusManagedAgents.map((agent) => {
                const draft = getDraftStatus(agent.agent_id, agent.status);
                const isBusy = statusBusyAgentId === agent.agent_id;
                return (
                  <div key={agent.agent_id} className="rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-sm">
                    <p className="font-medium text-[#141413]">{agent.agent_id}</p>
                    <p className="mt-1 text-xs text-[#6b6860]">{getAgentDisplayName(agent, isChinese)}</p>
                    <p className="mt-1 text-xs text-[#8a867d]">{agent.role}</p>
                    <div className="mt-2 flex items-center gap-2">
                      <select
                        data-testid={`agent-status-select-${agent.agent_id}`}
                        value={draft}
                        onChange={(event) =>
                          setStatusDrafts((prev) => ({
                            ...prev,
                            [agent.agent_id]: event.target.value as "online" | "offline" | "busy"
                          }))
                        }
                        className="rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs"
                      >
                        <option value="online">online</option>
                        <option value="busy">busy</option>
                        <option value="offline">offline</option>
                      </select>
                      <button
                        data-testid={`agent-status-save-${agent.agent_id}`}
                        type="button"
                        disabled={isBusy || draft === agent.status}
                        onClick={() => {
                          void onUpdateAgentStatus(agent.agent_id, draft);
                        }}
                        className="nexus-button-primary rounded-lg px-2 py-1 text-xs disabled:opacity-50"
                      >
                        {isBusy ? (isChinese ? "保存中..." : "Saving...") : isChinese ? "保存状态" : "Save"}
                      </button>
                    </div>
                  </div>
                );
              })}
              {statusManagedAgents.length === 0 ? (
                <p className="text-xs text-[#6b6860]">{isChinese ? "筛选后无可管理 Agent。" : "No agents match current status filter."}</p>
              ) : null}
            </div>
            {statusActionError ? <p className="mt-2 text-xs text-[#c0453a]">{statusActionError}</p> : null}
          </article>

          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "技能标签" : "Skill tags"}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {allSkills.length === 0 ? <p className="text-sm text-[#6b6860]">{isChinese ? "暂无技能标签。" : "No skills tagged yet."}</p> : null}
              {allSkills.map((skill) => (
                <span key={skill} className="rounded-full border border-[#d8d2c4] bg-[#f5f1e7] px-3 py-1 text-xs text-[#6b6860]">
                  {skill}
                </span>
              ))}
            </div>
          </article>

          <article className="nexus-panel p-4 text-sm leading-relaxed text-[#6b6860]">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "查看建议" : "What to check"}</p>
            <ul className="mt-3 space-y-2">
              <li>• {isChinese ? "先看谁在线、谁忙碌，判断当前执行容量。" : "Check who is online and busy to estimate execution capacity."}</li>
              <li>• {isChinese ? "按技能检索目标 Agent，再回到任务工作区执行或交接。" : "Filter by skills to find the right agent, then execute or handoff in task workspace."}</li>
              <li>• {isChinese ? "在角色分布中观察是否存在角色短缺。" : "Use role distribution to identify role gaps."}</li>
            </ul>
          </article>
        </div>
      </section>
    </main>
  );
}

const SKILL_QUERY_ALIASES: Record<string, string[]> = {
  "规划": ["plan", "planner", "workflow", "prioritize", "breakdown"],
  "计划": ["plan", "planner", "workflow"],
  "研究": ["research", "search", "analysis", "sources"],
  "分析": ["analysis", "insight", "evaluation", "risk"],
  "写作": ["write", "writer", "summary", "report", "edit"],
  "评审": ["review", "reviewer", "quality", "validation"],
  "仲裁": ["judge", "arbitration", "consensus", "decision"],
  "忙": ["busy"],
  "在线": ["online"],
  "离线": ["offline"]
};

const DISCOVER_QUICK_CHIPS = [
  { keyword: "规划", labelZh: "规划", labelEn: "Planning" },
  { keyword: "研究", labelZh: "研究", labelEn: "Research" },
  { keyword: "写作", labelZh: "写作", labelEn: "Writing" },
  { keyword: "评审", labelZh: "评审", labelEn: "Review" },
  { keyword: "仲裁", labelZh: "仲裁", labelEn: "Arbitration" }
];

function matchesAgentQuery(agent: { agent_id: string; name: string; role: string; skills: string[]; status: string }, rawQuery: string): boolean {
  const normalized = rawQuery.trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  const terms = new Set<string>([normalized]);
  Object.entries(SKILL_QUERY_ALIASES).forEach(([alias, mapped]) => {
    if (normalized.includes(alias)) {
      mapped.forEach((term) => terms.add(term));
    }
  });

  const candidates = [agent.agent_id, agent.name, agent.role, agent.status, ...agent.skills].map((item) => item.toLowerCase());
  return Array.from(terms).some((term) => candidates.some((candidate) => candidate.includes(term)));
}

