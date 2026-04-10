"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { apiClient, clearStoredAuthToken, getStoredAuthToken, setStoredAuthToken } from "@/lib/api/client";
import { getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";

type AuthTab = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const { isChinese } = useI18n();

  const [activeTab, setActiveTab] = useState<AuthTab>("login");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [registerUsername, setRegisterUsername] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerInviteCode, setRegisterInviteCode] = useState("");

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      return;
    }
    let cancelled = false;
    void apiClient
      .getCurrentUser()
      .then(() => {
        if (!cancelled) {
          router.replace("/");
        }
      })
      .catch(() => {
        clearStoredAuthToken();
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function onLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const response = await apiClient.loginUser({
        username: loginUsername.trim(),
        password: loginPassword
      });
      setStoredAuthToken(response.access_token);
      router.replace("/");
    } catch (err) {
      setMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setBusy(false);
    }
  }

  async function onRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const response = await apiClient.registerUser({
        username: registerUsername.trim(),
        password: registerPassword,
        invite_code: registerInviteCode.trim()
      });
      setStoredAuthToken(response.access_token);
      router.replace("/");
    } catch (err) {
      setMessage(getUserFacingErrorMessage(err, { isChinese, context: "backend" }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[720px] items-center px-4 py-10 md:px-6">
      <section className="nexus-panel w-full p-6 md:p-8">
        <p className="text-xs uppercase tracking-[0.18em] text-[#8a867d]">NexusAI</p>
        <h1 className="mt-2 text-2xl font-semibold text-[#141413]">{isChinese ? "登录系统" : "Sign in"}</h1>
        <p className="mt-2 text-sm text-[#6b6860]">
          {isChinese
            ? "登录后才可访问 Workspace。新用户需要邀请码完成注册。"
            : "You must sign in to access the workspace. New users need an invite code to register."}
        </p>

        <div className="mt-4 flex gap-2 rounded-xl border border-[#ddd7ca] bg-[#fff8ef] p-2">
          <button
            type="button"
            onClick={() => setActiveTab("login")}
            className={`rounded-lg px-3 py-1.5 text-xs ${activeTab === "login" ? "bg-[#141413] text-[#f5f3ec]" : "bg-[#f4efe4] text-[#6b6860]"}`}
          >
            {isChinese ? "登录" : "Login"}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("register")}
            className={`rounded-lg px-3 py-1.5 text-xs ${activeTab === "register" ? "bg-[#141413] text-[#f5f3ec]" : "bg-[#f4efe4] text-[#6b6860]"}`}
          >
            {isChinese ? "注册" : "Register"}
          </button>
        </div>

        {activeTab === "login" ? (
          <form className="mt-4 space-y-2" onSubmit={onLogin}>
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
            <button type="submit" disabled={busy} className="nexus-button-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50">
              {busy ? "..." : isChinese ? "登录" : "Sign in"}
            </button>
          </form>
        ) : (
          <form className="mt-4 space-y-2" onSubmit={onRegister}>
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
            <button type="submit" disabled={busy} className="nexus-button-primary rounded-lg px-4 py-2 text-sm disabled:opacity-50">
              {busy ? "..." : isChinese ? "注册并进入" : "Register & continue"}
            </button>
          </form>
        )}

        {message ? <p className="mt-3 text-sm text-[#c0453a]">{message}</p> : null}
      </section>
    </main>
  );
}



