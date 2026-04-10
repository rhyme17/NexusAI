"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient, getStoredAuthToken } from "@/lib/api/client";
import { AuthUser } from "@/lib/api/types";

export function useCurrentUser() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = getStoredAuthToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return null;
    }

    setIsLoading(true);
    try {
      const nextUser = await apiClient.getCurrentUser();
      setUser(nextUser);
      return nextUser;
    } catch {
      setUser(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { user, isLoading, refresh };
}

