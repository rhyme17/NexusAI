"use client";

import { useI18n } from "@/lib/i18n/language-context";

export function LanguageToggle() {
  const { locale, setLocale, text } = useI18n();

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-[#d8d2c4] bg-[#f5f3ec] px-2 py-1 text-xs text-[#6b6860]">
      <span className="font-medium">{text.languageToggleLabel}</span>
      <button
        type="button"
        onClick={() => setLocale("zh-CN")}
        className={`rounded-full px-2 py-1 transition ${
          locale === "zh-CN" ? "bg-[#141413] text-[#f5f3ec]" : "text-[#6b6860] hover:bg-[#ece9e0]"
        }`}
      >
        中文
      </button>
      <button
        type="button"
        onClick={() => setLocale("en")}
        className={`rounded-full px-2 py-1 transition ${
          locale === "en" ? "bg-[#141413] text-[#f5f3ec]" : "text-[#6b6860] hover:bg-[#ece9e0]"
        }`}
      >
        EN
      </button>
    </div>
  );
}

