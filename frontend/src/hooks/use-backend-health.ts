"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api/client";

export type BackendStatus = "checking" | "online" | "offline";

const ENABLE_NAV_CACHE = process.env.NODE_ENV !== "test";
const HEALTH_CACHE_TTL_MS = 5000;

type CachedHealth = {
  status: BackendStatus;
  readOnly: boolean;
  storageBackend: string | null;
  cachedAt: number;
};

let backendHealthCache: CachedHealth | null = null;
let backendHealthInFlight: Promise<CachedHealth> | null = null;

async function loadBackendHealthWithDedupe(force = false): Promise<CachedHealth> {
  if (!ENABLE_NAV_CACHE) {
    try {
      const response = await apiClient.getHealth();
      return {
        status: "online",
        readOnly: Boolean(response.read_only),
        storageBackend: typeof response.storage_backend === "string" ? response.storage_backend : null,
        cachedAt: Date.now()
      };
    } catch {
      return {
        status: "offline",
        readOnly: false,
        storageBackend: null,
        cachedAt: Date.now()
      };
    }
  }

  const now = Date.now();
  if (!force && backendHealthCache && now - backendHealthCache.cachedAt < HEALTH_CACHE_TTL_MS) {
    return backendHealthCache;
  }
  if (backendHealthInFlight) {
    return backendHealthInFlight;
  }

  backendHealthInFlight = (async () => {
    try {
      const response = await apiClient.getHealth();
      const next = {
        status: "online" as const,
        readOnly: Boolean(response.read_only),
        storageBackend: typeof response.storage_backend === "string" ? response.storage_backend : null,
        cachedAt: Date.now()
      };
      backendHealthCache = next;
      return next;
    } catch {
      const next = {
        status: "offline" as const,
        readOnly: false,
        storageBackend: null,
        cachedAt: Date.now()
      };
      backendHealthCache = next;
      return next;
    } finally {
      backendHealthInFlight = null;
    }
  })();

  return backendHealthInFlight;
}

export function useBackendHealth() {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [readOnly, setReadOnly] = useState(false);
  const [storageBackend, setStorageBackend] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const next = await loadBackendHealthWithDedupe(true);
    setStatus(next.status);
    setReadOnly(next.readOnly);
    setStorageBackend(next.storageBackend);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void loadBackendHealthWithDedupe(false).then((next) => {
      if (cancelled) {
        return;
      }
      setStatus(next.status);
      setReadOnly(next.readOnly);
      setStorageBackend(next.storageBackend);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return {
    status,
    readOnly,
    storageBackend,
    refresh
  };
}

