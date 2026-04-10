import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";
import { LanguageProvider } from "@/lib/i18n/language-context";
import { UserKeyProvider } from "@/lib/user-key-context";

export const metadata: Metadata = {
  title: "NexusAI 协作中枢",
  description: "多智能体协作与任务编排控制台"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <LanguageProvider>
          <UserKeyProvider>
            <AppShell>{children}</AppShell>
          </UserKeyProvider>
        </LanguageProvider>
      </body>
    </html>
  );
}

