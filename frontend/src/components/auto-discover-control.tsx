"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api/client";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface AutoDiscoverConfig {
  news_rate_seconds: number;
  task_rate_minutes: number;
  max_tasks_per_run: number;
  enabled: boolean;
}

interface AutoDiscoverRunResult {
  success: boolean;
  news_count: number;
  problems_count: number;
  tasks_created: number;
  tasks: Array<{ task_id: string; objective: string }>;
  message: string;
}

export function AutoDiscoverControl() {
  const { isChinese } = useI18n();
  const [config, setConfig] = useState<AutoDiscoverConfig>({
    news_rate_seconds: 60,
    task_rate_minutes: 60,
    max_tasks_per_run: 3,
    enabled: true,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AutoDiscoverRunResult | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  async function loadConfig() {
    try {
      const response = await fetch(`${API_BASE}/api/auto-discover/config`);
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (err) {
      console.error("Failed to load auto-discover config:", err);
    }
  }

  async function updateConfig(updates: Partial<AutoDiscoverConfig>) {
    setIsLoading(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE}/api/auto-discover/config`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...config, ...updates }),
      });
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
        setMessage(isChinese ? "配置已更新" : "Configuration updated");
      } else {
        setMessage(isChinese ? "更新失败" : "Update failed");
      }
    } catch (err) {
      setMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setIsLoading(false);
    }
  }

  async function runImmediate() {
    setIsRunning(true);
    setMessage(null);
    setLastResult(null);
    try {
      const response = await fetch(`${API_BASE}/api/auto-discover/run`, {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        setLastResult(data);
        setMessage(data.message);
      } else {
        setMessage(isChinese ? "执行失败" : "Execution failed");
      }
    } catch (err) {
      setMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <article className="nexus-panel p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">
        {isChinese ? "🤖 自动发现模式" : "🤖 Auto-Discover Mode"}
      </p>
      
      <div className="mt-3 rounded-lg border border-[#ddd7ca] bg-[#fffcf6] p-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-[#141413]">
              {isChinese ? "模式状态" : "Mode Status"}
            </p>
            <p className="text-xs text-[#6b6860]">
              {config.enabled
                ? (isChinese ? "自动发现模式已启用，AI将自主创建任务" : "Auto-discover enabled. AI will create tasks autonomously.")
                : (isChinese ? "自动发现模式已禁用，仅支持手动输入任务" : "Auto-discover disabled. Manual task input only.")}
            </p>
          </div>
          <button
            type="button"
            disabled={isLoading}
            onClick={() => updateConfig({ enabled: !config.enabled })}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
              config.enabled
                ? "border border-[#e6b6ad] bg-[#fff0ed] text-[#c0453a] hover:bg-[#ffe8e3]"
                : "border border-[#9bc5a7] bg-[#edf7ef] text-[#2f5d3e] hover:bg-[#e3f3e7]"
            } disabled:opacity-50`}
          >
            {config.enabled
              ? (isChinese ? "禁用模式" : "Disable")
              : (isChinese ? "启用模式" : "Enable")}
          </button>
        </div>
      </div>

      <div className="mt-4 space-y-3 text-xs text-[#6b6860]">
        <p className="font-medium text-[#141413]">{isChinese ? "速率配置" : "Rate Configuration"}</p>
        
        <div className="grid gap-3 md:grid-cols-3">
          <div className="flex items-center justify-between rounded-lg border border-[#ddd7ca] bg-[#fffcf6] p-2">
            <span>{isChinese ? "新闻间隔" : "News Interval"}</span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min={10}
                max={3600}
                value={config.news_rate_seconds}
                onChange={(e) => setConfig({ ...config, news_rate_seconds: parseInt(e.target.value) || 60 })}
                onBlur={() => updateConfig({ news_rate_seconds: config.news_rate_seconds })}
                className="w-14 rounded border border-[#d8d2c4] bg-[#fffdf9] px-1 py-0.5 text-right text-xs"
              />
              <span className="text-[10px]">{isChinese ? "秒" : "sec"}</span>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-[#ddd7ca] bg-[#fffcf6] p-2">
            <span>{isChinese ? "任务间隔" : "Task Interval"}</span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min={1}
                max={1440}
                value={config.task_rate_minutes}
                onChange={(e) => setConfig({ ...config, task_rate_minutes: parseInt(e.target.value) || 60 })}
                onBlur={() => updateConfig({ task_rate_minutes: config.task_rate_minutes })}
                className="w-14 rounded border border-[#d8d2c4] bg-[#fffdf9] px-1 py-0.5 text-right text-xs"
              />
              <span className="text-[10px]">{isChinese ? "分钟" : "min"}</span>
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-[#ddd7ca] bg-[#fffcf6] p-2">
            <span>{isChinese ? "每次任务数" : "Tasks/Run"}</span>
            <input
              type="number"
              min={1}
              max={10}
              value={config.max_tasks_per_run}
              onChange={(e) => setConfig({ ...config, max_tasks_per_run: parseInt(e.target.value) || 3 })}
              onBlur={() => updateConfig({ max_tasks_per_run: config.max_tasks_per_run })}
              className="w-14 rounded border border-[#d8d2c4] bg-[#fffdf9] px-1 py-0.5 text-right text-xs"
            />
          </div>
        </div>
      </div>

      <div className="mt-4 border-t border-[#ddd7ca] pt-4">
        <p className="text-xs font-medium text-[#141413]">{isChinese ? "演示控制" : "Demo Control"}</p>
        <p className="mt-1 text-[11px] text-[#8a867d]">
          {isChinese
            ? "点击按钮立即执行一次发现流程（忽略速率限制）"
            : "Click to run discovery immediately (ignores rate limits)"}
        </p>
        <button
          type="button"
          disabled={isRunning || !config.enabled}
          onClick={runImmediate}
          className="mt-2 w-full nexus-button-primary rounded-lg px-3 py-2 text-sm disabled:opacity-50"
        >
          {isRunning
            ? (isChinese ? "执行中..." : "Running...")
            : (isChinese ? "⚡ 立即执行（演示）" : "⚡ Run Immediately (Demo)")}
        </button>
      </div>

      {message ? (
        <p className={`mt-3 text-xs ${lastResult?.success ? "text-[#2f5d3e]" : "text-[#6b6860]"}`}>
          {message}
        </p>
      ) : null}

      {lastResult && lastResult.success ? (
        <div className="mt-3 rounded-lg border border-[#9bc5a7] bg-[#edf7ef] p-3 text-xs text-[#2f5d3e]">
          <p className="font-medium">{isChinese ? "执行结果" : "Result"}</p>
          <ul className="mt-2 space-y-1">
            <li>• {isChinese ? `获取新闻: ${lastResult.news_count} 条` : `News fetched: ${lastResult.news_count}`}</li>
            <li>• {isChinese ? `发现问题: ${lastResult.problems_count} 个` : `Problems found: ${lastResult.problems_count}`}</li>
            <li>• {isChinese ? `创建任务: ${lastResult.tasks_created} 个` : `Tasks created: ${lastResult.tasks_created}`}</li>
          </ul>
          {lastResult.tasks.length > 0 ? (
            <div className="mt-2 space-y-1">
              <p className="font-medium">{isChinese ? "新任务" : "New Tasks"}</p>
              {lastResult.tasks.map((task) => (
                <p key={task.task_id} className="truncate">
                  • {task.task_id}: {task.objective}
                </p>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 border-t border-[#ddd7ca] pt-4">
        <Link
          href="/auto-discover"
          className="block text-center text-xs text-[#d97757] hover:underline"
        >
          {isChinese ? "前往自动发现中心 →" : "Go to Auto-Discover Center →"}
        </Link>
      </div>
    </article>
  );
}
