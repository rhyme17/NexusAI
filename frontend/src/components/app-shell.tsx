"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { apiClient, clearStoredAuthToken, getStoredAuthToken } from "@/lib/api/client";
import { useI18n } from "@/lib/i18n/language-context";

interface AppShellProps {
  children: React.ReactNode;
}

interface NavItem {
  href: string;
  labelZh: string;
  labelEn: string;
  descriptionZh: string;
  descriptionEn: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    labelZh: "概览",
    labelEn: "Overview",
    descriptionZh: "先看整体状态，再决定下一步。",
    descriptionEn: "See the whole system before taking action."
  },
  {
    href: "/tasks",
    labelZh: "任务台",
    labelEn: "Tasks",
    descriptionZh: "创建任务、筛选任务、进入任务工作区。",
    descriptionEn: "Create, filter, and open task workspaces."
  },
  {
    href: "/agents",
    labelZh: "智能体",
    labelEn: "Agents",
    descriptionZh: "查看角色分工、状态与技能分布。",
    descriptionEn: "Inspect roles, readiness, and skills."
  },
  {
    href: "/settings",
    labelZh: "设置",
    labelEn: "Settings",
    descriptionZh: "管理账号安全、密钥、偏好和系统功能。",
    descriptionEn: "Manage account security, keys, preferences, and system features."
  }
];

function isActivePath(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { isChinese } = useI18n();
  const [authReady, setAuthReady] = useState(false);
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const verifiedTokenRef = useRef<string>("");

  const isLoginRoute = pathname === "/login" || pathname.startsWith("/login/");

  useEffect(() => {
    if (isLoginRoute) {
      setAuthReady(true);
      return;
    }

    const token = getStoredAuthToken();
    if (!token) {
      verifiedTokenRef.current = "";
      setAuthReady(false);
      router.replace("/login");
      return;
    }

    // Avoid re-validating the same token on every route change.
    if (verifiedTokenRef.current === token) {
      setAuthReady(true);
      return;
    }

    let cancelled = false;
    void apiClient
      .getCurrentUser()
      .then(() => {
        if (!cancelled) {
          verifiedTokenRef.current = token;
          setAuthReady(true);
        }
      })
      .catch(() => {
        verifiedTokenRef.current = "";
        clearStoredAuthToken();
        if (!cancelled) {
          setAuthReady(false);
          router.replace("/login");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isLoginRoute, router]);

  useEffect(() => {
    setPendingHref(null);
  }, [pathname]);

  useEffect(() => {
    if (!authReady || isLoginRoute) {
      return;
    }
    // Prefetch core workspace routes to reduce perceived latency on nav switching.
    NAV_ITEMS.forEach((item) => router.prefetch(item.href));
  }, [authReady, isLoginRoute, router]);

  if (isLoginRoute) {
    return <div className="min-h-screen">{children}</div>;
  }

  if (!authReady) {
    return (
      <div className="mx-auto flex min-h-screen w-full max-w-[900px] items-center justify-center px-6 py-10">
        <div className="nexus-panel rounded-2xl p-6 text-sm text-[#6b6860]">{isChinese ? "正在验证登录状态..." : "Checking authentication..."}</div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-4 px-4 py-4 md:px-6 xl:grid xl:grid-cols-[280px_minmax(0,1fr)] xl:gap-6 xl:px-8 xl:py-6">
      <aside className="nexus-panel flex flex-col gap-5 p-4 xl:sticky xl:top-6 xl:h-[calc(100vh-3rem)] xl:overflow-y-auto xl:p-5">
        <div className="space-y-3 border-b border-[#ddd7ca] pb-4">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-[#e2d8c9] bg-[#fff7f1] text-sm font-semibold text-[#c96544]">
            NA
          </div>
          <h1 className="text-xl font-semibold text-[#141413]">{isChinese ? "玄枢" : "NexusAI"}</h1>
        </div>

        <nav className="space-y-2" aria-label={isChinese ? "主导航" : "Primary navigation"}>
          <p className="px-1 text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "工作区" : "Workspace"}</p>
          <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
            {NAV_ITEMS.map((item) => {
              const active = isActivePath(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onMouseEnter={() => {
                    router.prefetch(item.href);
                  }}
                  onFocus={() => {
                    router.prefetch(item.href);
                  }}
                  onClick={() => {
                    if (!active) {
                      setPendingHref(item.href);
                    }
                  }}
                  className={`rounded-2xl border p-3 transition ${
                    active
                      ? "border-[#d97757] bg-[#fff4ee] shadow-[0_10px_24px_rgba(217,119,87,0.12)]"
                      : "border-[#ddd7ca] bg-[#fffcf6] hover:border-[#c8bfaf] hover:bg-[#fff9f1]"
                  }`}
                  aria-current={active ? "page" : undefined}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-[#141413]">{isChinese ? item.labelZh : item.labelEn}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] ${
                        active ? "bg-[#d97757] text-white" : "bg-[#f2ece1] text-[#6b6860]"
                      }`}
                    >
                      {active
                        ? isChinese
                          ? "当前"
                          : "Open"
                        : pendingHref === item.href
                          ? isChinese
                            ? "进入中"
                            : "Opening"
                          : isChinese
                            ? "进入"
                            : "Visit"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-[#6b6860]">
                    {isChinese ? item.descriptionZh : item.descriptionEn}
                  </p>
                </Link>
              );
            })}
          </div>
        </nav>

        <div className="rounded-2xl border border-[#ddd7ca] bg-[#fffcf6] p-4 text-sm text-[#3e3a35]">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "使用建议" : "Usage tip"}</p>
          <p className="mt-2 leading-relaxed text-[#6b6860]">
            {isChinese
              ? "先在任务台创建任务，再进入任务工作区执行与查看事件流，最后到智能体页查看协作网络。"
              : "Create a task in Tasks, run it in the task workspace, then inspect the collaboration network in Agents."}
          </p>
        </div>
      </aside>

      <div className="min-w-0">{children}</div>
    </div>
  );
}

