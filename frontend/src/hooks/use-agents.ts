"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api/client";
import { Agent } from "@/lib/api/types";

interface UseAgentsOptions {
  skill?: string;
  status?: "online" | "offline" | "busy";
}

const ENABLE_NAV_CACHE = process.env.NODE_ENV !== "test";
const AGENTS_CACHE_TTL_MS = 10000;

const agentsCache = new Map<string, { data: Agent[]; cachedAt: number }>();
const agentsInFlight = new Map<string, Promise<Agent[]>>();

function buildAgentsCacheKey(options?: UseAgentsOptions): string {
  return JSON.stringify({ skill: options?.skill ?? null, status: options?.status ?? null });
}

async function loadAgentsWithDedupe(options?: UseAgentsOptions, force = false): Promise<Agent[]> {
  if (!ENABLE_NAV_CACHE) {
    return apiClient.listAgents({ skill: options?.skill, status: options?.status });
  }
  const key = buildAgentsCacheKey(options);
  const now = Date.now();
  const cached = agentsCache.get(key);
  if (!force && cached && now - cached.cachedAt < AGENTS_CACHE_TTL_MS) {
    return cached.data;
  }
  const pending = agentsInFlight.get(key);
  if (pending) {
    return pending;
  }
  const nextPromise = apiClient
    .listAgents({ skill: options?.skill, status: options?.status })
    .then((nextAgents) => {
      agentsCache.set(key, { data: nextAgents, cachedAt: Date.now() });
      return nextAgents;
    })
    .finally(() => {
      agentsInFlight.delete(key);
    });
  agentsInFlight.set(key, nextPromise);
  return nextPromise;
}

export function useAgents(options?: UseAgentsOptions) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextAgents = await loadAgentsWithDedupe(options, true);
      setAgents(nextAgents);
    } catch (err) {
      setAgents([]);
      setError(err instanceof Error ? err : new Error("Failed to fetch agents"));
    } finally {
      setIsLoading(false);
    }
  }, [options?.skill, options?.status]);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void loadAgentsWithDedupe(options, false)
      .then((nextAgents) => {
        if (!cancelled) {
          setAgents(nextAgents);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setAgents([]);
          setError(err instanceof Error ? err : new Error("Failed to fetch agents"));
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [options?.skill, options?.status]);

  return {
    agents,
    isLoading,
    error,
    refresh
  };
}

