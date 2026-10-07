"use client";

import { TrendingUp } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { PageHeader, PageSkeleton } from "@/components/page-header";
import {
  type Opportunity,
  type PipelineStage,
  useAssignOpportunityOwner,
  useOpportunities,
  usePipelineSummary,
  useRevenueAttribution,
  useTransitionOpportunityStage,
} from "@/hooks/use-opportunities";

const STAGE_BADGE_VARIANT: Record<
  PipelineStage,
  "secondary" | "warning" | "success" | "destructive"
> = {
  QUALIFIED: "secondary",
  DISCOVERY: "secondary",
  EVALUATION: "warning",
  PROPOSAL: "warning",
  NEGOTIATION: "warning",
  WON: "success",
  LOST: "destructive",
};

//: The linear pipeline `colt_application.opportunity_state.OPPORTUNITY_TRANSITIONS` enforces
//: server-side — this is only the UI's own "what's the obvious next step" shortcut, never the
//: authority on what's allowed (the API call itself is).
const NEXT_STAGE: Record<PipelineStage, PipelineStage | null> = {
  QUALIFIED: "DISCOVERY",
  DISCOVERY: "EVALUATION",
  EVALUATION: "PROPOSAL",
  PROPOSAL: "NEGOTIATION",
  NEGOTIATION: "WON",
  WON: null,
  LOST: null,
};

const CLOSED_STAGES = new Set<PipelineStage>(["WON", "LOST"]);

function PipelineSummaryRow() {
  const { data: stages, isLoading } = usePipelineSummary();

  if (isLoading) return <PageSkeleton />;
  if (!stages) return null;

  return (
    <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
      {stages.map((stage) => (
        <Card key={stage.stage}>
          <CardContent className="py-4">
            <Badge variant={STAGE_BADGE_VARIANT[stage.stage]}>{stage.stage}</Badge>
            <p className="mt-2 text-2xl font-semibold">{stage.count}</p>
            <p className="text-xs text-muted-foreground">
              {stage.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function RevenueAttributionTable() {
  const { data: rows, isLoading } = useRevenueAttribution();

  if (isLoading) return null;
  if (!rows || rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No closed-won revenue yet.</p>;
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-muted-foreground">
          <th className="py-1">Source</th>
          <th className="py-1">Currency</th>
          <th className="py-1 text-right">Total value</th>
          <th className="py-1 text-right">Opportunities</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr className="border-t border-border" key={`${row.source}-${row.currency}`}>
            <td className="py-1.5">{row.source}</td>
            <td className="py-1.5">{row.currency ?? "—"}</td>
            <td className="py-1.5 text-right">
              {row.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              {row.includes_estimate ? (
                <span className="ml-1 text-xs text-muted-foreground">(incl. estimate)</span>
              ) : null}
            </td>
            <td className="py-1.5 text-right">{row.opportunity_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
  const transitionStage = useTransitionOpportunityStage();
  const assignOwner = useAssignOpportunityOwner();
  const [ownerId, setOwnerId] = useState("");

  const closed = CLOSED_STAGES.has(opportunity.pipeline_stage);
  const nextStage = NEXT_STAGE[opportunity.pipeline_stage];

  const handleAssignOwner = (event: React.FormEvent) => {
    event.preventDefault();
    if (!ownerId.trim()) return;
    assignOwner.mutate(
      { opportunityId: opportunity.id, ownerId: ownerId.trim() },
      { onSuccess: () => setOwnerId("") },
    );
  };

  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant={STAGE_BADGE_VARIANT[opportunity.pipeline_stage]}>
                {opportunity.pipeline_stage}
              </Badge>
              {opportunity.estimated_value != null ? (
                <span className="font-medium">
                  {opportunity.estimated_value.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}{" "}
                  {opportunity.currency}
                  {opportunity.is_estimated_value ? (
                    <span className="ml-1 text-xs text-muted-foreground">(estimate)</span>
                  ) : null}
                </span>
              ) : (
                <span className="text-sm text-muted-foreground">No value yet</span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {opportunity.owner_id ? `Owner: ${opportunity.owner_id}` : "Unassigned"} ·{" "}
              {opportunity.source ?? "unknown source"}
            </p>
          </div>
          {!closed && (
            <div className="flex gap-2">
              {nextStage ? (
                <Button
                  disabled={transitionStage.isPending}
                  onClick={() =>
                    transitionStage.mutate({
                      opportunityId: opportunity.id,
                      targetStage: nextStage,
                    })
                  }
                  size="sm"
                  variant="outline"
                >
                  Advance to {nextStage}
                </Button>
              ) : null}
              <Button
                disabled={transitionStage.isPending}
                onClick={() =>
                  transitionStage.mutate({ opportunityId: opportunity.id, targetStage: "LOST" })
                }
                size="sm"
                variant="outline"
              >
                Mark lost
              </Button>
            </div>
          )}
        </div>
        {!closed && (
          <form
            className="mt-3 flex items-end gap-2 border-t border-border pt-3"
            onSubmit={handleAssignOwner}
          >
            <label className="flex flex-col gap-1 text-xs">
              Assign owner (user id)
              <input
                className="h-8 w-64 rounded-md border border-input bg-background px-2 text-xs"
                onChange={(event) => setOwnerId(event.target.value)}
                placeholder="user uuid"
                value={ownerId}
              />
            </label>
            <Button disabled={assignOwner.isPending} size="sm" type="submit" variant="outline">
              Assign
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * The Opportunity engine's UI (CLAUDE.md §10.14, §11.3, §68 Milestone 21): the pipeline
 * dashboard — per-stage counts and value, revenue attribution by source, and per-opportunity
 * stage transition/owner assignment — the frontend half of the same lifecycle
 * `tests/integration/test_opportunity_engine.py` proves against real Postgres.
 *
 * Real data end to end, through the typed `@colt/api-client` generated from the live OpenAPI
 * schema — but this page cannot be exercised live in this environment: there is no Keycloak
 * login flow here, so every request 401s with no real bearer token to attach. Type-checked
 * against the real schema is what's verified; a logged-in browser session is not.
 */
export function OpportunitiesPage() {
  const { data: opportunities, isLoading, isError } = useOpportunities();

  return (
    <div>
      <PageHeader
        title="Opportunities"
        description="Pipeline stages, revenue attribution, and owner assignment for commercial opportunities."
      />

      <PipelineSummaryRow />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Revenue attribution</CardTitle>
        </CardHeader>
        <CardContent>
          <RevenueAttributionTable />
        </CardContent>
      </Card>

      {isLoading ? (
        <PageSkeleton />
      ) : isError ? (
        <EmptyState
          icon={TrendingUp}
          title="Could not load opportunities"
          description="The API request failed — in this environment, that's expected without a logged-in session (no Keycloak flow is wired up here)."
        />
      ) : opportunities && opportunities.length > 0 ? (
        <ul className="space-y-3">
          {opportunities.map((opportunity) => (
            <li key={opportunity.id}>
              <OpportunityCard opportunity={opportunity} />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={TrendingUp}
          title="No opportunities yet"
          description="A positive conversation with enough commercial intent creates one automatically (OpportunityAgent, CLAUDE.md §12.11)."
        />
      )}
    </div>
  );
}
