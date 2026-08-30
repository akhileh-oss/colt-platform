"use client";

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

export interface SystemHealth {
  live: boolean;
  ready: boolean;
  checks: Record<string, { ready: boolean; detail: string | null }>;
}

async function fetchSystemHealth(): Promise<SystemHealth> {
  const [liveResult, readyResult] = await Promise.all([
    apiClient.GET("/live"),
    apiClient.GET("/ready"),
  ]);

  const checks: SystemHealth["checks"] = {};
  for (const [name, check] of Object.entries(readyResult.data?.checks ?? {})) {
    checks[name] = { ready: check.ready, detail: check.detail ?? null };
  }

  return {
    live: !liveResult.error && liveResult.data?.status === "alive",
    ready: !readyResult.error && readyResult.data?.status === "ready",
    checks,
  };
}

/**
 * Live system health for the dashboard's "system health" panel (CLAUDE.md §43.1) — real data
 * from the probes built in Milestone 02, refetched on an interval and on window focus.
 */
export function useSystemHealth() {
  return useQuery({
    queryKey: ["system-health"],
    queryFn: fetchSystemHealth,
    refetchInterval: 15_000,
  });
}
