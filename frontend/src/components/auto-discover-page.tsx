"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n/language-context";

interface NewsItem {
  title: string;
  link: string;
  description: string;
  source_name: string;
  category: string;
  pub_date: string | null;
}

interface ProblemItem {
  title: string;
  source: string;
  type: string;
  keyword_found: string;
  priority: number;
  description: string;
  timestamp: string;
  source_name: string | null;
  category: string | null;
}

interface AutoDiscoverConfig {
  news_rate_seconds: number;
  task_rate_minutes: number;
  max_tasks_per_run: number;
  enabled: boolean;
}

interface AutoDiscoverStatus {
  enabled: boolean;
  running: boolean;
  last_run_time: string | null;
  last_task_time: string | null;
  config: AutoDiscoverConfig;
  news_count: number;
  problems_count: number;
}

interface RunResult {
  success: boolean;
  news_count: number;
  problems_count: number;
  tasks_created: number;
  tasks: Array<{ task_id: string; objective: string }>;
  message: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function AutoDiscoverPage() {
  const { isChinese } = useI18n();
  
  const [status, setStatus] = useState<AutoDiscoverStatus | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [problems, setProblems] = useState<ProblemItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isFetchingNews, setIsFetchingNews] = useState(false);
  const [lastResult, setLastResult] = useState<RunResult | null>(null);
  const [activeTab, setActiveTab] = useState<"news" | "problems" | "tasks">("news");
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [selectedProblem, setSelectedProblem] = useState<ProblemItem | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [sources, setSources] = useState<string[]>([]);

  useEffect(() => {
    loadStatus();
  }, []);

  async function loadStatus() {
    try {
      const response = await fetch(`${API_BASE}/api/auto-discover/status`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (err) {
      console.error("Failed to load status:", err);
    }
  }

  async function fetchNews() {
    setIsFetchingNews(true);
    try {
      const response = await fetch(`${API_BASE}/api/auto-discover/fetch-news`, {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        setNews(data.items);
        setSources(data.sources);
      }
    } catch (err) {
      console.error("Failed to fetch news:", err);
    } finally {
      setIsFetchingNews(false);
    }
  }

  async function runDiscovery() {
    setIsRunning(true);
    setLastResult(null);
    try {
      const response = await fetch(`${API_BASE}/api/auto-discover/run`, {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        setLastResult(data);
        if (data.success) {
          await loadStatus();
        }
      }
    } catch (err) {
      console.error("Failed to run discovery:", err);
    } finally {
      setIsRunning(false);
    }
  }

  async function toggleEnabled() {
    if (!status) return;
    try {
      const endpoint = status.enabled ? "disable" : "enable";
      await fetch(`${API_BASE}/api/auto-discover/${endpoint}`, {
        method: "POST",
      });
      await loadStatus();
    } catch (err) {
      console.error("Failed to toggle:", err);
    }
  }

  const filteredNews = news.filter(
    (item) => categoryFilter === "all" || item.category === categoryFilter
  );

  const getPriorityColor = (priority: number) => {
    if (priority >= 80) return "text-[#c0453a] bg-[#fff0ed] border-[#e6b6ad]";
    if (priority >= 60) return "text-[#9a6a34] bg-[#fff7ec] border-[#e5d0b4]";
    return "text-[#6b6860] bg-[#f4efe4] border-[#d8d2c4]";
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      opportunity: isChinese ? "机遇" : "opportunity",
      problem: isChinese ? "问题" : "problem",
      trend: isChinese ? "趋势" : "trend",
      conflict: isChinese ? "冲突" : "conflict",
      innovation: isChinese ? "创新" : "innovation",
    };
    return labels[type] || type;
  };

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      technology: isChinese ? "科技" : "technology",
      world: isChinese ? "国际" : "world",
      general: isChinese ? "综合" : "general",
    };
    return labels[category] || category;
  };

  return (
    <main className="space-y-6 pb-3">
      <header className="nexus-panel relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full bg-[#d97757]/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl space-y-2">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">
              {isChinese ? "工作区 / 自动发现" : "Workspace / Auto-Discover"}
            </p>
            <h1 className="text-2xl font-semibold text-[#141413] md:text-3xl">
              {isChinese ? "🤖 AI 自主发现中心" : "🤖 AI Auto-Discovery Center"}
            </h1>
            <p className="text-sm leading-relaxed text-[#6b6860] md:text-base">
              {isChinese
                ? "AI自动浏览新闻源，分析发现问题，生成任务。与手动输入模式完全独立。"
                : "AI automatically browses news, analyzes problems, and generates tasks. Fully independent from manual input mode."}
            </p>
          </div>
          
          <div className="grid min-w-[220px] gap-2 rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-4 text-sm text-[#6b6860]">
            <div className="flex items-center justify-between">
              <span>{isChinese ? "状态" : "Status"}</span>
              <span className={`font-medium ${status?.enabled ? "text-[#2f5d3e]" : "text-[#c0453a]"}`}>
                {status?.enabled ? (isChinese ? "已启用" : "Enabled") : (isChinese ? "已禁用" : "Disabled")}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>{isChinese ? "新闻源" : "Sources"}</span>
              <span className="font-medium text-[#141413]">{sources.length}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>{isChinese ? "发现问题" : "Problems"}</span>
              <span className="font-medium text-[#141413]">{status?.problems_count || 0}</span>
            </div>
          </div>
        </div>
      </header>

      <section className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
        <div className="space-y-4">
          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">
              {isChinese ? "控制面板" : "Control Panel"}
            </p>
            
            <div className="mt-4 space-y-3">
              <button
                onClick={toggleEnabled}
                className={`w-full rounded-lg px-3 py-2 text-sm font-medium transition ${
                  status?.enabled
                    ? "border border-[#e6b6ad] bg-[#fff0ed] text-[#c0453a] hover:bg-[#ffe8e3]"
                    : "border border-[#9bc5a7] bg-[#edf7ef] text-[#2f5d3e] hover:bg-[#e3f3e7]"
                }`}
              >
                {status?.enabled
                  ? (isChinese ? "🔴 禁用自动发现" : "🔴 Disable Auto-Discover")
                  : (isChinese ? "🟢 启用自动发现" : "🟢 Enable Auto-Discover")}
              </button>

              <button
                onClick={fetchNews}
                disabled={isFetchingNews}
                className="w-full nexus-button-ghost rounded-lg px-3 py-2 text-sm disabled:opacity-50"
              >
                {isFetchingNews
                  ? (isChinese ? "获取中..." : "Fetching...")
                  : (isChinese ? "📡 获取最新新闻" : "📡 Fetch Latest News")}
              </button>

              <button
                onClick={runDiscovery}
                disabled={isRunning || !status?.enabled}
                className="w-full nexus-button-primary rounded-lg px-3 py-2 text-sm disabled:opacity-50"
              >
                {isRunning
                  ? (isChinese ? "执行中..." : "Running...")
                  : (isChinese ? "⚡ 立即执行发现" : "⚡ Run Discovery Now")}
              </button>
            </div>

            {lastResult && (
              <div className={`mt-4 rounded-lg p-3 text-xs ${
                lastResult.success
                  ? "border border-[#9bc5a7] bg-[#edf7ef] text-[#2f5d3e]"
                  : "border border-[#e6b6ad] bg-[#fff0ed] text-[#c0453a]"
              }`}>
                <p className="font-medium">{lastResult.message}</p>
                {lastResult.success && (
                  <ul className="mt-2 space-y-1">
                    <li>• {isChinese ? `新闻: ${lastResult.news_count}` : `News: ${lastResult.news_count}`}</li>
                    <li>• {isChinese ? `问题: ${lastResult.problems_count}` : `Problems: ${lastResult.problems_count}`}</li>
                    <li>• {isChinese ? `任务: ${lastResult.tasks_created}` : `Tasks: ${lastResult.tasks_created}`}</li>
                  </ul>
                )}
              </div>
            )}
          </article>

          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">
              {isChinese ? "配置参数" : "Configuration"}
            </p>
            <div className="mt-3 space-y-2 text-xs text-[#6b6860]">
              <div className="flex justify-between">
                <span>{isChinese ? "新闻间隔" : "News interval"}</span>
                <span className="font-medium text-[#141413]">{status?.config.news_rate_seconds}s</span>
              </div>
              <div className="flex justify-between">
                <span>{isChinese ? "任务间隔" : "Task interval"}</span>
                <span className="font-medium text-[#141413]">{status?.config.task_rate_minutes}min</span>
              </div>
              <div className="flex justify-between">
                <span>{isChinese ? "每次任务数" : "Tasks per run"}</span>
                <span className="font-medium text-[#141413]">{status?.config.max_tasks_per_run}</span>
              </div>
            </div>
            <Link
              href="/settings"
              className="mt-3 block text-center text-xs text-[#d97757] hover:underline"
            >
              {isChinese ? "在设置中修改 →" : "Modify in Settings →"}
            </Link>
          </article>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-2 border-b border-[#ddd7ca] pb-2">
            <button
              onClick={() => setActiveTab("news")}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                activeTab === "news"
                  ? "bg-[#d97757] text-white"
                  : "text-[#6b6860] hover:bg-[#f4efe4]"
              }`}
            >
              {isChinese ? "📰 新闻列表" : "📰 News"} ({news.length})
            </button>
            <button
              onClick={() => setActiveTab("problems")}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                activeTab === "problems"
                  ? "bg-[#d97757] text-white"
                  : "text-[#6b6860] hover:bg-[#f4efe4]"
              }`}
            >
              {isChinese ? "🔍 发现问题" : "🔍 Problems"} ({problems.length})
            </button>
            <button
              onClick={() => setActiveTab("tasks")}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                activeTab === "tasks"
                  ? "bg-[#d97757] text-white"
                  : "text-[#6b6860] hover:bg-[#f4efe4]"
              }`}
            >
              {isChinese ? "📋 已创建任务" : "📋 Tasks"}
            </button>
          </div>

          {activeTab === "news" && (
            <section className="nexus-panel p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-[#8a867d]">
                  {isChinese ? "新闻列表" : "News List"}
                </h2>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="rounded-lg border border-[#d8d2c4] bg-[#fffcf6] px-2 py-1 text-xs"
                >
                  <option value="all">{isChinese ? "全部分类" : "All Categories"}</option>
                  <option value="technology">{isChinese ? "科技" : "Technology"}</option>
                  <option value="world">{isChinese ? "国际" : "World"}</option>
                  <option value="general">{isChinese ? "综合" : "General"}</option>
                </select>
              </div>

              {news.length === 0 ? (
                <div className="py-8 text-center text-sm text-[#6b6860]">
                  <p>{isChinese ? '暂无新闻，点击"获取最新新闻"按钮' : "No news yet. Click 'Fetch Latest News'"}</p>
                </div>
              ) : (
                <ul className="max-h-[60vh] space-y-2 overflow-y-auto">
                  {filteredNews.map((item, index) => (
                    <li key={index}>
                      <button
                        onClick={() => setSelectedNews(selectedNews === item ? null : item)}
                        className={`w-full rounded-xl border p-3 text-left transition ${
                          selectedNews === item
                            ? "border-[#d97757] bg-[#fff5f1]"
                            : "border-[#ddd7ca] bg-[#fffcf6] hover:border-[#c7c0b1]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium text-[#141413] line-clamp-2">{item.title}</p>
                          <span className="shrink-0 rounded-full bg-[#f4efe4] px-2 py-0.5 text-[10px] text-[#6b6860]">
                            {getCategoryLabel(item.category)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-[#8a867d]">
                          {item.source_name}
                        </p>
                        {selectedNews === item && (
                          <div className="mt-3 space-y-2 border-t border-[#ddd7ca] pt-3">
                            <p className="text-xs text-[#6b6860]">{item.description}</p>
                            <a
                              href={item.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-block text-xs text-[#d97757] hover:underline"
                            >
                              {isChinese ? "查看原文 →" : "Read more →"}
                            </a>
                          </div>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {activeTab === "problems" && (
            <section className="nexus-panel p-4">
              <div className="mb-3">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-[#8a867d]">
                  {isChinese ? "发现的问题/机会" : "Discovered Problems/Opportunities"}
                </h2>
              </div>

              {problems.length === 0 ? (
                <div className="py-8 text-center text-sm text-[#6b6860]">
                  <p>{isChinese ? "暂无发现问题，执行发现后显示" : "No problems yet. Run discovery first."}</p>
                </div>
              ) : (
                <ul className="max-h-[60vh] space-y-2 overflow-y-auto">
                  {problems.map((item, index) => (
                    <li key={index}>
                      <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium text-[#141413] line-clamp-2">{item.title}</p>
                          <div className="flex shrink-0 gap-1">
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] ${getPriorityColor(item.priority)}`}>
                              {isChinese ? `优先级: ${item.priority}` : `P${item.priority}`}
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span className="rounded-full bg-[#d97757]/10 px-2 py-0.5 text-[10px] text-[#d97757]">
                            {getTypeLabel(item.type)}
                          </span>
                          <span className="text-[10px] text-[#8a867d]">
                            {isChinese ? "关键词" : "Keyword"}: {item.keyword_found}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-[#6b6860]">{item.description}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {activeTab === "tasks" && (
            <section className="nexus-panel p-4">
              <div className="mb-3">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-[#8a867d]">
                  {isChinese ? "自动创建的任务" : "Auto-Created Tasks"}
                </h2>
              </div>

              {lastResult?.tasks && lastResult.tasks.length > 0 ? (
                <ul className="space-y-2">
                  {lastResult.tasks.map((task) => (
                    <li key={task.task_id}>
                      <Link
                        href={`/tasks/${task.task_id}`}
                        className="block rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 transition hover:border-[#c7c0b1]"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-medium text-[#141413] line-clamp-2">{task.objective}</p>
                          <span className="shrink-0 rounded-full bg-[#9bc5a7]/20 px-2 py-0.5 text-[10px] text-[#2f5d3e]">
                            🤖 auto
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-[#8a867d]">{task.task_id}</p>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="py-8 text-center text-sm text-[#6b6860]">
                  <p>{isChinese ? "暂无自动创建的任务" : "No auto-created tasks yet"}</p>
                  <Link href="/tasks" className="mt-2 inline-block text-xs text-[#d97757] hover:underline">
                    {isChinese ? "查看所有任务 →" : "View all tasks →"}
                  </Link>
                </div>
              )}
            </section>
          )}
        </div>
      </section>
    </main>
  );
}
