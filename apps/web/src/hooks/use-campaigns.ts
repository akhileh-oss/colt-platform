"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@colt/api-client";

import { apiClient } from "@/api/client";

export type Campaign = components["schemas"]["CampaignResponse"];
export type CreateCampaignRequest = components["schemas"]["CreateCampaignRequest"];
export type SequenceStep = components["schemas"]["SequenceStepResponse"];
export type AddSequenceStepRequest = components["schemas"]["AddSequenceStepRequest"];

const CAMPAIGNS_QUERY_KEY = ["campaigns"] as const;
const sequenceStepsQueryKey = (campaignId: string) => ["campaigns", campaignId, "sequence-steps"];

async function fetchCampaigns(): Promise<Campaign[]> {
  const { data, error } = await apiClient.GET("/api/v1/campaigns");
  if (error) throw error;
  return data.campaigns;
}

/**
 * This organization's campaigns (CLAUDE.md §10.9, §68 Milestone 14) — real data from the
 * Campaign engine's REST surface, typed end-to-end from the generated OpenAPI schema.
 */
export function useCampaigns() {
  return useQuery({ queryKey: CAMPAIGNS_QUERY_KEY, queryFn: fetchCampaigns });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateCampaignRequest) => {
      const { data, error } = await apiClient.POST("/api/v1/campaigns", { body });
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CAMPAIGNS_QUERY_KEY }),
  });
}

export function useValidateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (campaignId: string) => {
      const { data, error } = await apiClient.POST("/api/v1/campaigns/{campaign_id}/validate", {
        params: { path: { campaign_id: campaignId } },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CAMPAIGNS_QUERY_KEY }),
  });
}

export function usePauseCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (campaignId: string) => {
      const { data, error } = await apiClient.POST("/api/v1/campaigns/{campaign_id}/pause", {
        params: { path: { campaign_id: campaignId } },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CAMPAIGNS_QUERY_KEY }),
  });
}

export function useResumeCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (campaignId: string) => {
      const { data, error } = await apiClient.POST("/api/v1/campaigns/{campaign_id}/resume", {
        params: { path: { campaign_id: campaignId } },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CAMPAIGNS_QUERY_KEY }),
  });
}

/** A campaign's ordered sequence steps (CLAUDE.md §10.10, §68 Milestone 14). */
export function useSequenceSteps(campaignId: string) {
  return useQuery({
    queryKey: sequenceStepsQueryKey(campaignId),
    queryFn: async () => {
      const { data, error } = await apiClient.GET(
        "/api/v1/campaigns/{campaign_id}/sequence-steps",
        { params: { path: { campaign_id: campaignId } } },
      );
      if (error) throw error;
      return data.sequence_steps;
    },
  });
}

export function useAddSequenceStep(campaignId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AddSequenceStepRequest) => {
      const { data, error } = await apiClient.POST(
        "/api/v1/campaigns/{campaign_id}/sequence-steps",
        { params: { path: { campaign_id: campaignId } }, body },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sequenceStepsQueryKey(campaignId) }),
  });
}
