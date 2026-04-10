"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "nexusai.user_modelscope_access_token";

interface UserKeyContextValue {
  userApiKey: string;
  setUserApiKey: (next: string) => void;
  clearUserApiKey: () => void;
  hasUserApiKey: boolean;
}

const UserKeyContext = createContext<UserKeyContextValue | null>(null);

export function UserKeyProvider({ children }: { children: React.ReactNode }) {
  const [userApiKey, setUserApiKeyState] = useState("");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && stored.trim()) {
      setUserApiKeyState(stored);
    }
  }, []);

  const value = useMemo<UserKeyContextValue>(() => {
    return {
      userApiKey,
      setUserApiKey: (next: string) => {
        const normalized = next.trim();
        setUserApiKeyState(normalized);
        if (normalized) {
          window.localStorage.setItem(STORAGE_KEY, normalized);
        } else {
          window.localStorage.removeItem(STORAGE_KEY);
        }
      },
      clearUserApiKey: () => {
        setUserApiKeyState("");
        window.localStorage.removeItem(STORAGE_KEY);
      },
      hasUserApiKey: Boolean(userApiKey)
    };
  }, [userApiKey]);

  return <UserKeyContext.Provider value={value}>{children}</UserKeyContext.Provider>;
}

export function useUserKey() {
  const context = useContext(UserKeyContext);
  if (!context) {
    throw new Error("useUserKey must be used within UserKeyProvider");
  }
  return context;
}

