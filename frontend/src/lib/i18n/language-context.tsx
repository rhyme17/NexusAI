"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { Locale, messages } from "./messages";

const STORAGE_KEY = "nexusai.locale";

interface LanguageContextValue {
  locale: Locale;
  setLocale: (next: Locale) => void;
  isChinese: boolean;
  text: (typeof messages)[Locale];
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh-CN");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "zh-CN" || stored === "en") {
      setLocaleState(stored);
    }
  }, []);

  const value = useMemo<LanguageContextValue>(() => {
    return {
      locale,
      setLocale: (next: Locale) => {
        setLocaleState(next);
        window.localStorage.setItem(STORAGE_KEY, next);
      },
      isChinese: locale === "zh-CN",
      text: messages[locale]
    };
  }, [locale]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useI18n must be used within LanguageProvider");
  }
  return context;
}

