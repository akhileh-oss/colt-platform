"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@colt/api-client";

import { apiClient } from "@/api/client";

export type Opportunity = components["schemas"]["OpportunityResponse"];
export type PipelineStage = components["schemas"]["PipelineStage"];
export type PipelineStageSummary = components["schemas"]["PipelineStageSummaryResponse"];
export type RevenueAttributionRow = components["schemas"]["RevenueAttributionRowResponse"];
export type TransitionOpportunityStageRequest =
  components["schemas"]["TransitionOpportunityStageRequest"];
export type AssignOpportunityOwnerRequest = components["schemas"]["AssignOpportunityOwnerRequest"];

const OPPORTUNITIES_QUERY_KEY = ["opportunities"] as const;
const PIPELINE_QUERY_KEY = ["opportunities", "pipeline"] as const;
const REVENUE_ATTRIBUTION_QUERY_KEY = ["opportunities", "revenue-attribution"] as const;

async function fetchOpportunities(): Promise<Opportunity[]> {
  const { data, error } = await apiClient.GET("/api/v1/opportunities");
  if (error) throw error;
  return data.opportunities;
}

/**
 * This organization's opportunities (CLAUDE.md §10.14, §11.3, §68 Milestone 21) — real data
 * from the Opportunity engine's REST surface, typed end-to-end from the generated OpenAPI
 * schema.
 */
export function useOpportunities() {
  return useQuery({ queryKey: OPPORTUNITIES_QUERY_KEY, queryFn: fetchOpportunities });
}

/** Per-stage counts and open value (CLAUDE.md §68 Milestone 21's "pipeline dashboard"). */
export function usePipelineSummary() {
  return useQuery({
    queryKey: PIPELINE_QUERY_KEY,
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/opportunities/pipeline");
      if (error) throw error;
      return data.stages;
    },
  });
}

/** Closed-won revenue grouped by source (CLAUDE.md §68 Milestone 21's "revenue attribution"). */
export function useRevenueAttribution() {
  return useQuery({
    queryKey: REVENUE_ATTRIBUTION_QUERY_KEY,
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/opportunities/revenue-attribution");
      if (error) throw error;
      return data.rows;
    },
  });
}

function useInvalidateOpportunities() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: OPPORTUNITIES_QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: PIPELINE_QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: REVENUE_ATTRIBUTION_QUERY_KEY });
  };
}

export function useTransitionOpportunityStage() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: async ({
      opportunityId,
      targetStage,
    }: {
      opportunityId: string;
      targetStage: PipelineStage;
    }) => {
      const { data, error } = await apiClient.POST(
        "/api/v1/opportunities/{opportunity_id}/transition",
        {
          params: { path: { opportunity_id: opportunityId } },
          body: { target_stage: targetStage },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: invalidate,
  });
}

export function useAssignOpportunityOwner() {
  const invalidate = useInvalidateOpportunities();
  return useMutation({
    mutationFn: async ({ opportunityId, ownerId }: { opportunityId: string; ownerId: string }) => {
      const { data, error } = await apiClient.POST(
        "/api/v1/opportunities/{opportunity_id}/assign-owner",
        {
          params: { path: { opportunity_id: opportunityId } },
          body: { owner_id: ownerId },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: invalidate,
  });
}
