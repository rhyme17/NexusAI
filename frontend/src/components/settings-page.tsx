"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useAgents } from "@/hooks/use-agents";
import { apiClient, clearStoredAuthToken, getStoredAuthToken, setStoredAuthToken } from "@/lib/api/client";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";
import { useUserKey } from "@/lib/user-key-context";
import { AuthUser, InviteCode } from "@/lib/api/types";
import { LanguageToggle } from "./language-toggle";

const PRESET_SKILLS = [
  "plan",
  "breakdown",
  "workflow",
  "prioritize",
  "research",
  "search",
  "analysis",
  "sources",
  "write",
  "summary",
  "report",
  "edit",
  "review",
  "quality",
  "validation",
  "risk",
  "evaluation",
  "insight",
  "decision",
  "consensus"
];

export function SettingsPage() {
  const router = useRouter();
  const { isChinese } = useI18n();
  const { userApiKey, setUserApiKey, clearUserApiKey, hasUserApiKey } = useUserKey();
  const { agents, refresh } = useAgents();

  const [draftUserApiKey, setDraftUserApiKey] = useState(userApiKey);
  // backend API key input removed from UI — keys should be managed server-side or via secure admin flow
  const [clearBusy, setClearBusy] = useState(false);
  const [clearMessage, setClearMessage] = useState<string | null>(null);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);

  const [registerName, setRegisterName] = useState("");
  const [registerRole, setRegisterRole] = useState("");
  const [registerSelectedSkills, setRegisterSelectedSkills] = useState<string[]>([]);
  const [registerCustomSkills, setRegisterCustomSkills] = useState("");
  const [registerBusy, setRegisterBusy] = useState(false);
  const [registerMessage, setRegisterMessage] = useState<string | null>(null);
  const [healthCheckBusy, setHealthCheckBusy] = useState(false);
  const [healthCheckMessage, setHealthCheckMessage] = useState<string | null>(null);

  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authMessage, setAuthMessage] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerInviteCode, setRegisterInviteCode] = useState("");
  const [invites, setInvites] = useState<InviteCode[]>([]);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteCodeDraft, setInviteCodeDraft] = useState("");
  const [inviteMaxUses, setInviteMaxUses] = useState("1");
  const [inviteExpiresHours, setInviteExpiresHours] = useState("72");
  const [adminBusy, setAdminBusy] = useState(false);
  const [resetPasswordMap, setResetPasswordMap] = useState<Record<string, string>>({});

  useEffect(() => {
    setDraftUserApiKey(userApiKey);
  }, [userApiKey]);

  // backend API key is no longer handled in the frontend settings.

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      return;
    }
    void loadCurrentUser();
  }, []);

  const skillOptions = useMemo(() => {
    const fromAgents = agents.flatMap((agent) => agent.skills);
    return Array.from(new Set([...PRESET_SKILLS, ...fromAgents])).sort((left, right) => left.localeCompare(right));
  }, [agents]);

  function toggleRegisterSkill(skill: string) {
    setRegisterSelectedSkills((prev) => (prev.includes(skill) ? prev.filter((item) => item !== skill) : [...prev, skill]));
  }

  function saveUserApiKey() {
    setUserApiKey(draftUserApiKey);
    setSettingsMessage(
      isChinese
        ? `用户 AI Key 已${draftUserApiKey.trim() ? "保存" : "清空"}。`
        : `User AI key ${draftUserApiKey.trim() ? "saved" : "cleared"}.`
    );
  }

  // backend key save/clear removed

  async function runClearServerData(options: { clearEventsOnly: boolean; restoreSeed: boolean }) {
    setClearBusy(true);
    setClearMessage(null);
    try {
      const response = await apiClient.clearServerData({
        keepDefaultAgents: true,
        clearEventsOnly: options.clearEventsOnly,
        restoreSeed: options.restoreSeed
      });
      const tasks = response.counts?.tasks ?? 0;
      const events = response.counts?.events ?? 0;
      setClearMessage(
        isChinese
          ? `已清理服务器数据：tasks=${tasks}, events=${events}${response.seed_restored ? "，并已恢复默认智能体" : ""}`
          : `Server data cleared: tasks=${tasks}, events=${events}${response.seed_restored ? ", default agents restored" : ""}`
      );
    } catch (err) {
      const message = getUserFacingErrorMessage(err, { isChinese, context: "backend" });
      setClearMessage(
        isChinese
          ? `清理失败：请确认后端已开启 NEXUSAI_DEBUG_API_ENABLED=true，并且当前角色具有管理员权限。(${message})`
          : `Clear failed: ensure backend sets NEXUSAI_DEBUG_API_ENABLED=true and the current role has admin access. (${message})`
      );
    } finally {
      setClearBusy(false);
    }
  }

  async function runConnectionCheck() {
    setHealthCheckBusy(true);
    setHealthCheckMessage(null);
    try {
      const health = await apiClient.getHealth();
      setHealthCheckMessage(
        isChinese
          ? `连接正常：status=${health.status}${health.storage_backend ? `, backend=${health.storage_backend}` : ""}`
          : `Connected: status=${health.status}${health.storage_backend ? `, backend=${health.storage_backend}` : ""}`
      );
    } catch (err) {
      setHealthCheckMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setHealthCheckBusy(false);
    }
  }

  async function loadCurrentUser() {
    try {
      const me = await apiClient.getCurrentUser();
      setAuthUser(me);
      if (me.role === "admin") {
        const inviteItems = await apiClient.listInvites();
        const userItems = await apiClient.listUsers();
        setInvites(inviteItems);
        setUsers(userItems);
      } else {
        setInvites([]);
        setUsers([]);
      }
    } catch {
      clearStoredAuthToken();
      setAuthUser(null);
      setInvites([]);
      setUsers([]);
    }
  }

  async function onLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthMessage(null);
    try {
      const response = await apiClient.loginUser({
        username: loginUsername.trim(),
        password: loginPassword
      });
      setStoredAuthToken(response.access_token);
      setAuthUser(response.user);
      setLoginPassword("");
      setAuthMessage(isChinese ? `登录成功：${response.user.username}` : `Signed in as ${response.user.username}`);
      if (response.user.role === "admin") {
        setInvites(await apiClient.listInvites());
        setUsers(await apiClient.listUsers());
      }
    } catch (err) {
      setAuthMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setAuthBusy(false);
    }
  }

  async function onRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthMessage(null);
    try {
      const response = await apiClient.registerUser({
        username: registerUsername.trim(),
        password: registerPassword,
        invite_code: registerInviteCode.trim()
      });
      setStoredAuthToken(response.access_token);
      setAuthUser(response.user);
      setRegisterPassword("");
      setRegisterInviteCode("");
      setAuthMessage(isChinese ? `注册成功：${response.user.username}` : `Registered as ${response.user.username}`);
      if (response.user.role === "admin") {
        setInvites(await apiClient.listInvites());
        setUsers(await apiClient.listUsers());
      }
    } catch (err) {
      setAuthMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setAuthBusy(false);
    }
  }

  async function onLogout() {
    setAuthBusy(true);
    setAuthMessage(null);
    try {
      await apiClient.logoutUser();
    } catch {
      // Ignore remote logout errors and clear local auth state.
    } finally {
      clearStoredAuthToken();
      setAuthUser(null);
      setInvites([]);
      setUsers([]);
      setAuthBusy(false);
      setAuthMessage(null);
      router.replace("/login");
    }
  }

  async function onDeleteOwnAccount() {
    const confirmed = window.confirm(
      isChinese
        ? "确认注销当前账户？该操作将删除你名下的任务，且无法恢复。"
        : "Delete this account? This will remove tasks owned by you and cannot be undone."
    );
    if (!confirmed) {
      return;
    }

    setAuthBusy(true);
    setAuthMessage(null);
    try {
      await apiClient.deleteOwnAccount();
      clearStoredAuthToken();
      setAuthUser(null);
      setInvites([]);
      setUsers([]);
      router.replace("/login");
    } catch (err) {
      setAuthMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setAuthBusy(false);
    }
  }

  async function onCreateInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setInviteBusy(true);
    setAuthMessage(null);
    try {
      await apiClient.createInvite({
        code: inviteCodeDraft.trim() || undefined,
        max_uses: Number.parseInt(inviteMaxUses, 10) || 1,
        expires_hours: Number.parseInt(inviteExpiresHours, 10) || 72
      });
      setInviteCodeDraft("");
      const items = await apiClient.listInvites();
      setInvites(items);
      setAuthMessage(isChinese ? "邀请码已创建。" : "Invite created.");
    } catch (err) {
      setAuthMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setInviteBusy(false);
    }
  }

  async function onRevokeInvite(code: string) {
    setAdminBusy(true);
    setAuthMessage(null);
    try {
      await apiClient.revokeInvite(code);
      setInvites(await apiClient.listInvites());
      setAuthMessage(isChinese ? `邀请码已作废：${code}` : `Invite revoked: ${code}`);
    } catch (err) {
      setAuthMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setAdminBusy(false);
    }
  }

  async function onToggleUserStatus(user: AuthUser, nextActive: boolean) {
    setAdminBusy(true);
    setAuthMessage(null);
    try {
      await apiClient.updateUserStatus(user.username, { is_active: nextActive });
      setUsers(await apiClient.listUsers());
      setAuthMessage(
        isChinese
          ? `${user.username} 已${nextActive ? "启用" : "禁用"}`
          : `${user.username} ${nextActive ? "enabled" : "disabled"}`
      );
    } catch (err) {
      setAuthMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setAdminBusy(false);
    }
  }

  async function onResetUserPassword(username: string) {
    const nextPassword = (resetPasswordMap[username] ?? "").trim();
    if (nextPassword.length < 8) {
      setAuthMessage(isChinese ? "新密码至少 8 位。" : "New password must be at least 8 characters.");
      return;
    }

    setAdminBusy(true);
    setAuthMessage(null);
    try {
      await apiClient.resetUserPassword(username, { new_password: nextPassword });
      setResetPasswordMap((prev) => ({ ...prev, [username]: "" }));
      setAuthMessage(isChinese ? `已重置 ${username} 的密码。` : `Password reset for ${username}.`);
    } catch (err) {
      setAuthMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setAdminBusy(false);
    }
  }

  async function runDangerousAction(
    options: { clearEventsOnly: boolean; restoreSeed: boolean },
    label: string
  ) {
    const confirmed = window.confirm(
      isChinese
        ? `即将执行高风险操作：${label}。此操作可能影响任务数据，是否继续？`
        : `You are about to run a high-risk operation: ${label}. This may change task data. Continue?`
    );
    if (!confirmed) {
      return;
    }
    const token = window.prompt(isChinese ? "请输入 CONFIRM 以继续" : "Type CONFIRM to continue", "");
    if (token !== "CONFIRM") {
      setClearMessage(isChinese ? "已取消：确认口令不匹配。" : "Cancelled: confirmation token mismatch.");
      return;
    }
    const auditId = `op_${Date.now().toString(36)}`;
    setClearMessage(isChinese ? `操作已确认，审计ID=${auditId}，正在执行...` : `Operation confirmed, audit id=${auditId}, running...`);
    await runClearServerData(options);
  }

  async function onRegisterAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!registerName.trim() || !registerRole.trim()) {
      setRegisterMessage(isChinese ? "请填写名称和角色。" : "Please provide both name and role.");
      return;
    }

    const customSkills = registerCustomSkills
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
    const skills = Array.from(new Set([...registerSelectedSkills, ...customSkills]));

    setRegisterBusy(true);
    setRegisterMessage(null);
    try {
      await apiClient.registerAgent({
        name: registerName.trim(),
        role: registerRole.trim(),
        skills,
        metadata: { source: "frontend_settings" }
      });
      setRegisterName("");
      setRegisterRole("");
      setRegisterSelectedSkills([]);
      setRegisterCustomSkills("");
      setRegisterMessage(isChinese ? "Agent 注册成功。" : "Agent registered.");
      await refresh();
    } catch (err) {
      setRegisterMessage(
        getUserFacingErrorMessage(err, {
          isChinese,
          context: "agents",
          fallback: isChinese ? "创建 Agent 失败。" : "Failed to register agent."
        })
      );
    } finally {
      setRegisterBusy(false);
    }
  }

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  return (
    <main className="space-y-6 pb-3">
      <header className="nexus-panel relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute -right-12 -top-10 h-40 w-40 rounded-full bg-[#d97757]/10 blur-3xl" />
        <div className="relative space-y-2">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">Workspace / Settings</p>
          <h1 className="text-2xl font-semibold text-[#141413] md:text-3xl">{isChinese ? "系统设置" : "Settings"}</h1>
          <p className="text-sm leading-relaxed text-[#6b6860] md:text-base">
            {isChinese
              ? "统一管理账号安全、语言偏好、模型连接、Agent 配置与系统管理。"
              : "Manage account security, language preferences, model connectivity, agent setup, and system controls in one place."}
          </p>
        </div>
      </header>

      <section className="nexus-panel p-3 text-xs text-[#8a867d]">
        {isChinese ? "一、账号与访问" : "1. Account & Access"}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "账户系统" : "Account"}</p>
          <p className="mt-2 text-xs text-[#6b6860]">
            {authUser
              ? isChinese
                ? `当前用户：${authUser.username}（${authUser.role}）`
                : `Signed in: ${authUser.username} (${authUser.role})`
              : isChinese
                ? "当前未登录。"
                : "Not signed in."}
          </p>
          {!authUser ? (
            <form className="mt-3 space-y-2" onSubmit={onLogin}>
              <input
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                placeholder={isChinese ? "用户名" : "Username"}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
              />
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder={isChinese ? "密码" : "Password"}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
              />
              <button type="submit" disabled={authBusy} className="nexus-button-primary rounded-lg px-3 py-1.5 text-xs disabled:opacity-50">
                {authBusy ? "..." : isChinese ? "登录" : "Sign in"}
              </button>
            </form>
          ) : (
            <div className="mt-3">
              <button type="button" onClick={() => void onLogout()} className="rounded-lg border border-[#d8d2c4] bg-[#f4efe4] px-3 py-1.5 text-xs text-[#6b6860]">
                {isChinese ? "退出登录" : "Sign out"}
              </button>
              {authUser.role !== "admin" ? (
                <button
                  type="button"
                  disabled={authBusy}
                  onClick={() => {
                    void onDeleteOwnAccount();
                  }}
                  className="ml-2 rounded-lg border border-[#e6b6ad] bg-[#fff0ed] px-3 py-1.5 text-xs text-[#c0453a] disabled:opacity-50"
                >
                  {isChinese ? "注销账户" : "Delete account"}
                </button>
              ) : null}
            </div>
          )}
          {authMessage ? <p className="mt-2 text-xs text-[#6b6860]">{authMessage}</p> : null}
        </article>

        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "邀请码注册" : "Register with invite"}</p>
          <form className="mt-3 space-y-2" onSubmit={onRegister}>
            <input
              value={registerUsername}
              onChange={(event) => setRegisterUsername(event.target.value)}
              placeholder={isChinese ? "新用户名" : "New username"}
              className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
            />
            <input
              type="password"
              value={registerPassword}
              onChange={(event) => setRegisterPassword(event.target.value)}
              placeholder={isChinese ? "密码（至少8位）" : "Password (min 8 chars)"}
              className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
            />
            <input
              value={registerInviteCode}
              onChange={(event) => setRegisterInviteCode(event.target.value)}
              placeholder={isChinese ? "邀请码" : "Invite code"}
              className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
            />
            <button type="submit" disabled={authBusy} className="nexus-button-primary rounded-lg px-3 py-1.5 text-xs disabled:opacity-50">
              {authBusy ? "..." : isChinese ? "注册并登录" : "Register & sign in"}
            </button>
          </form>
        </article>
      </section>

      {authUser?.role === "admin" ? (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "创建邀请码（管理员）" : "Create invite (admin)"}</p>
            <form className="mt-3 grid gap-2" onSubmit={onCreateInvite}>
              <input
                value={inviteCodeDraft}
                onChange={(event) => setInviteCodeDraft(event.target.value)}
                placeholder={isChinese ? "自定义邀请码（可选）" : "Custom invite code (optional)"}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
              />
              <input
                value={inviteMaxUses}
                onChange={(event) => setInviteMaxUses(event.target.value)}
                placeholder={isChinese ? "可使用次数" : "Max uses"}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
              />
              <input
                value={inviteExpiresHours}
                onChange={(event) => setInviteExpiresHours(event.target.value)}
                placeholder={isChinese ? "有效期（小时）" : "Expires in hours"}
                className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm"
              />
              <button type="submit" disabled={inviteBusy} className="nexus-button-primary rounded-lg px-3 py-1.5 text-xs disabled:opacity-50">
                {inviteBusy ? "..." : isChinese ? "创建邀请码" : "Create invite"}
              </button>
            </form>
          </article>

          <article className="nexus-panel p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "邀请码列表" : "Invite list"}</p>
            {invites.length === 0 ? (
              <p className="mt-2 text-xs text-[#6b6860]">{isChinese ? "暂无邀请码。" : "No invites yet."}</p>
            ) : (
              <div className="mt-2 max-h-48 overflow-y-auto rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs text-[#3e3a35]">
                {invites.map((item) => (
                  <p key={item.code} className="mb-2">
                    {item.code} • {item.used_count}/{item.max_uses}
                    {item.expires_at ? ` • ${new Date(item.expires_at).toLocaleString()}` : ""}
                    <button
                      type="button"
                      disabled={adminBusy}
                      onClick={() => {
                        void onRevokeInvite(item.code);
                      }}
                      className="ml-2 rounded border border-[#e6b6ad] bg-[#fff0ed] px-1.5 py-0.5 text-[10px] text-[#c0453a] disabled:opacity-50"
                    >
                      {isChinese ? "作废" : "Revoke"}
                    </button>
                  </p>
                ))}
              </div>
            )}
          </article>
        </section>
      ) : null}

      {authUser?.role === "admin" ? (
        <section className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "用户管理（管理员）" : "User management (admin)"}</p>
          {users.length === 0 ? (
            <p className="mt-2 text-xs text-[#6b6860]">{isChinese ? "暂无用户。" : "No users."}</p>
          ) : (
            <div className="mt-2 max-h-72 space-y-2 overflow-y-auto rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2">
              {users.map((user) => (
                <div key={user.user_id} className="rounded-lg border border-[#ddd7ca] bg-[#fff8ef] p-2 text-xs text-[#3e3a35]">
                  <p>
                    {user.username} • {user.role} • {user.is_active ? (isChinese ? "启用" : "active") : (isChinese ? "禁用" : "disabled")}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={adminBusy || user.username === authUser.username}
                      onClick={() => {
                        void onToggleUserStatus(user, !user.is_active);
                      }}
                      className="rounded border border-[#d8d2c4] bg-[#f4efe4] px-2 py-1 text-[11px] text-[#6b6860] disabled:opacity-50"
                    >
                      {user.is_active ? (isChinese ? "禁用" : "Disable") : (isChinese ? "启用" : "Enable")}
                    </button>
                    <input
                      type="password"
                      value={resetPasswordMap[user.username] ?? ""}
                      onChange={(event) =>
                        setResetPasswordMap((prev) => ({
                          ...prev,
                          [user.username]: event.target.value
                        }))
                      }
                      placeholder={isChinese ? "新密码" : "New password"}
                      className="rounded border border-[#d8d2c4] bg-[#fffcf6] px-2 py-1 text-[11px]"
                    />
                    <button
                      type="button"
                      disabled={adminBusy}
                      onClick={() => {
                        void onResetUserPassword(user.username);
                      }}
                      className="rounded border border-[#9bc5a7] bg-[#edf7ef] px-2 py-1 text-[11px] text-[#2f5d3e] disabled:opacity-50"
                    >
                      {isChinese ? "重置密码" : "Reset password"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      <section className="nexus-panel p-3 text-xs text-[#8a867d]">
        {isChinese ? "二、工作区偏好与连接" : "2. Preferences & Connectivity"}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "语言设置" : "Language"}</p>
          <div className="mt-3">
            <LanguageToggle />
          </div>
        </article>

        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "环境信息" : "Environment"}</p>
          <p className="mt-3 text-sm text-[#6b6860]">
            {isChinese ? "后端地址" : "Backend base URL"}: <span className="font-medium text-[#141413]">{apiBaseUrl}</span>
          </p>
          <p className="mt-2 text-xs text-[#8a867d]">
            {isChinese
              ? "密钥仅保存在当前浏览器本地存储，不会自动同步到其他设备。"
              : "Keys are stored only in this browser local storage and are not synced automatically."}
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              disabled={healthCheckBusy}
              onClick={() => {
                void runConnectionCheck();
              }}
              className="nexus-button-ghost rounded-lg px-3 py-1.5 text-xs disabled:opacity-50"
            >
              {healthCheckBusy ? (isChinese ? "检测中..." : "Checking...") : isChinese ? "连接测试" : "Test connection"}
            </button>
            {healthCheckMessage ? <span className="text-xs text-[#6b6860]">{healthCheckMessage}</span> : null}
          </div>
        </article>
      </section>

      <section className="nexus-panel p-3 text-xs text-[#8a867d]">
        {isChinese ? "三、模型与 API 密钥" : "3. Model & API Keys"}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "用户 AI Key" : "User AI key"}</p>
          <p className="mt-2 text-xs text-[#6b6860]">
            {isChinese
              ? `当前状态：${hasUserApiKey ? "已配置 MODELSCOPE_ACCESS_TOKEN" : "未配置"}`
              : `Status: ${hasUserApiKey ? "MODELSCOPE_ACCESS_TOKEN configured" : "not configured"}`}
          </p>
          <input
            type="password"
            value={draftUserApiKey}
            onChange={(event) => setDraftUserApiKey(event.target.value)}
            className="mt-3 w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
            placeholder={isChinese ? "输入你的 MODELSCOPE_ACCESS_TOKEN" : "Enter your MODELSCOPE_ACCESS_TOKEN"}
            autoComplete="off"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={saveUserApiKey} className="nexus-button-primary rounded-lg px-3 py-1.5 text-xs">
              {isChinese ? "保存" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => {
                clearUserApiKey();
                setDraftUserApiKey("");
                setSettingsMessage(isChinese ? "用户 AI Key 已清空。" : "User AI key cleared.");
              }}
              className="rounded-lg border border-[#d8d2c4] bg-[#f4efe4] px-3 py-1.5 text-xs text-[#6b6860]"
            >
              {isChinese ? "清除" : "Clear"}
            </button>
          </div>
        </article>

        {/* Backend API key UI removed — backend/admin keys must be provisioned server-side. */}
      </section>

      {settingsMessage ? <p className="nexus-panel p-3 text-sm text-[#6b6860]">{settingsMessage}</p> : null}

      <section className="nexus-panel p-3 text-xs text-[#8a867d]">
        {isChinese ? "四、Agent 配置" : "4. Agent Configuration"}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)]">
        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "注册 Agent" : "Register agent"}</p>
          <form className="mt-3 space-y-3" onSubmit={onRegisterAgent}>
            <input
              value={registerName}
              onChange={(event) => setRegisterName(event.target.value)}
              placeholder={isChinese ? "名称，例如 planner-2" : "Name, e.g. planner-2"}
              className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
            />
            <input
              value={registerRole}
              onChange={(event) => setRegisterRole(event.target.value)}
              placeholder={isChinese ? "角色，例如 planner" : "Role, e.g. planner"}
              className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
            />
            <div>
              <p className="text-xs text-[#6b6860]">{isChinese ? "技能（可多选）" : "Skills (multi-select)"}</p>
              <div className="mt-2 max-h-40 overflow-y-auto rounded-xl border border-[#d8d2c4] bg-[#fffdf9] p-2">
                <div className="flex flex-wrap gap-2">
                  {skillOptions.map((skill) => {
                    const active = registerSelectedSkills.includes(skill);
                    return (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => toggleRegisterSkill(skill)}
                        className={`rounded-full border px-2 py-1 text-xs ${
                          active ? "border-[#d97757] bg-[#fff1eb] text-[#b95535]" : "border-[#d8d2c4] bg-[#f5f1e7] text-[#6b6860]"
                        }`}
                      >
                        {skill}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            <input
              value={registerCustomSkills}
              onChange={(event) => setRegisterCustomSkills(event.target.value)}
              placeholder={isChinese ? "补充技能（逗号分隔，可选）" : "Additional skills (comma separated, optional)"}
              className="w-full rounded-xl border border-[#d8d2c4] bg-[#fffcf6] px-3 py-2 text-sm text-[#3e3a35]"
            />
            <button type="submit" disabled={registerBusy} className="nexus-button-primary rounded-xl px-3 py-2 text-sm disabled:opacity-50">
              {registerBusy ? (isChinese ? "创建中..." : "Creating...") : isChinese ? "注册 Agent" : "Register agent"}
            </button>
          </form>
          {registerMessage ? <p className="mt-2 text-xs text-[#6b6860]">{registerMessage}</p> : null}
        </article>
      </section>

      <section className="nexus-panel p-3 text-xs text-[#8a867d]">
        {isChinese ? "五、管理员与系统管理" : "5. Admin & System"}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "服务器数据管理" : "Server data controls"}</p>
          <p className="mt-2 text-xs text-[#8a867d]">
            {isChinese
              ? "该区域包含高风险操作，建议仅由管理员在确认后执行。"
              : "This section contains high-impact operations and should be used by admins only."}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={clearBusy}
              onClick={() => {
                void runDangerousAction({ clearEventsOnly: true, restoreSeed: false }, isChinese ? "仅清空事件" : "Clear events");
              }}
              className="rounded-lg border border-[#d8d2c4] bg-[#f4efe4] px-2 py-1 text-[11px] text-[#6b6860] disabled:opacity-50"
            >
              {isChinese ? "仅清空事件" : "Clear events"}
            </button>
            <button
              type="button"
              disabled={clearBusy}
              onClick={() => {
                void runDangerousAction(
                  { clearEventsOnly: false, restoreSeed: false },
                  isChinese ? "清空任务+事件" : "Clear tasks+events"
                );
              }}
              className="rounded-lg border border-[#e6b6ad] bg-[#fff0ed] px-2 py-1 text-[11px] text-[#c0453a] disabled:opacity-50"
            >
              {isChinese ? "清空任务+事件" : "Clear tasks+events"}
            </button>
            <button
              type="button"
              disabled={clearBusy}
              onClick={() => {
                void runDangerousAction(
                  { clearEventsOnly: false, restoreSeed: true },
                  isChinese ? "重置并恢复默认智能体" : "Reset + restore default agents"
                );
              }}
              className="rounded-lg border border-[#9bc5a7] bg-[#edf7ef] px-2 py-1 text-[11px] text-[#2f5d3e] disabled:opacity-50"
            >
              {isChinese ? "重置并恢复默认智能体" : "Reset + restore default agents"}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-[#8a867d]">
            {isChinese
              ? "所有高风险操作都需要二次确认；执行前会生成审计ID提示，便于追踪。"
              : "All high-risk operations require double confirmation and emit an audit id hint before execution."}
          </p>
          {clearMessage ? <p className="mt-2 text-xs text-[#6b6860]">{clearMessage}</p> : null}
        </article>

        <article className="nexus-panel p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-[#8a867d]">{isChinese ? "建议新增设置" : "Suggested additions"}</p>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-[#6b6860]">
            <li>• {isChinese ? "通知设置：任务失败/完成时邮件或站内提醒。" : "Notifications: email or in-app alerts on task failure/completion."}</li>
            <li>• {isChinese ? "结果保存策略：自动导出为 .md/.txt 并保留历史版本。" : "Result retention: auto-export to .md/.txt with version history."}</li>
            <li>• {isChinese ? "默认执行策略：为新任务预设执行模式、回退策略和仲裁策略。" : "Default execution policy: preset mode, fallback, and arbitration for new tasks."}</li>
            <li>• {isChinese ? "界面偏好：紧凑/舒适密度、默认首页模块显示开关。" : "UI preferences: compact/comfortable density and homepage module toggles."}</li>
          </ul>
        </article>
      </section>
    </main>
  );
}

