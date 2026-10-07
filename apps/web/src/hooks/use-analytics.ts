"use client";

import { useQuery } from "@tanstack/react-query";

import type { components } from "@colt/api-client";

import { apiClient } from "@/api/client";

export type FunnelStage = components["schemas"]["FunnelResponse"];
export type IcpPerformanceRow = components["schemas"]["IcpPerformanceResponse"];
export type TriggerPerformanceRow = components["schemas"]["TriggerPerformanceResponse"];
export type MessagePerformanceRow = components["schemas"]["MessagePerformanceResponse"];
export type ChannelPerformanceRow = components["schemas"]["ChannelPerformanceResponse"];
export type AgentCostRow = components["schemas"]["AgentCostResponse"];
export type ModelPerformanceRow = components["schemas"]["ModelPerformanceResponse"];
export type RevenueOutcomeRow = components["schemas"]["RevenueOutcomeResponse"];

/**
 * The Analytics + Learning Loop dashboard's data (CLAUDE.md §68, Milestone 22) — one hook per
 * `/api/v1/analytics/*` route, each a thin `useQuery` over the typed `@colt/api-client`, mirroring
 * `use-opportunities.ts`'s established shape. Every hook is read-only; there is nothing here to
 * invalidate or mutate.
 */
export function useFunnel() {
  return useQuery({
    queryKey: ["analytics", "funnel"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/funnel");
      if (error) throw error;
      return data.stages;
    },
  });
}

export function useIcpPerformance() {
  return useQuery({
    queryKey: ["analytics", "icp-performance"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/icp-performance");
      if (error) throw error;
      return data.rows;
    },
  });
}

export function useTriggerPerformance() {
  return useQuery({
    queryKey: ["analytics", "trigger-performance"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/trigger-performance");
      if (error) throw error;
      return data.rows;
    },
  });
}

export function useMessagePerformance() {
  return useQuery({
    queryKey: ["analytics", "message-performance"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/message-performance");
      if (error) throw error;
      return data.rows;
    },
  });
}

export function useChannelPerformance() {
  return useQuery({
    queryKey: ["analytics", "channel-performance"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/channel-performance");
      if (error) throw error;
      return data.rows;
    },
  });
}

export function useAgentCost() {
  return useQuery({
    queryKey: ["analytics", "agent-cost"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/agent-cost");
      if (error) throw error;
      return data.rows;
    },
  });
}

export function useModelPerformance() {
  return useQuery({
    queryKey: ["analytics", "model-performance"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/model-performance");
      if (error) throw error;
      return data.rows;
    },
  });
}

export function useRevenueOutcomes() {
  return useQuery({
    queryKey: ["analytics", "revenue-outcomes"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/analytics/revenue-outcomes");
      if (error) throw error;
      return data.rows;
    },
  });
}
