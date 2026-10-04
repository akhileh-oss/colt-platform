"use client";

import { Target } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { PageHeader, PageSkeleton } from "@/components/page-header";
import {
  type Campaign,
  useAddSequenceStep,
  useCampaigns,
  useCreateCampaign,
  usePauseCampaign,
  useResumeCampaign,
  useSequenceSteps,
  useValidateCampaign,
} from "@/hooks/use-campaigns";

const STATUS_BADGE_VARIANT: Record<Campaign["status"], "secondary" | "success" | "warning"> = {
  DRAFT: "secondary",
  ACTIVE: "success",
  PAUSED: "warning",
  COMPLETED: "secondary",
  ARCHIVED: "secondary",
};

function SequenceSteps({ campaignId }: { campaignId: string }) {
  const { data: steps, isLoading } = useSequenceSteps(campaignId);
  const addStep = useAddSequenceStep(campaignId);
  const [channel, setChannel] = useState("");
  const [strategy, setStrategy] = useState("");

  const nextOrder = steps?.length ?? 0;

  const handleAdd = (event: React.FormEvent) => {
    event.preventDefault();
    if (!channel.trim() || !strategy.trim()) return;
    addStep.mutate(
      {
        step_order: nextOrder,
        channel: channel.trim(),
        message_strategy: strategy.trim(),
        delay_after_previous: 0,
        active: true,
      },
      {
        onSuccess: () => {
          setChannel("");
          setStrategy("");
        },
      },
    );
  };

  return (
    <div className="mt-3 border-t border-border pt-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Sequence steps</p>
      {isLoading ? (
        <p className="text-xs text-muted-foreground">Loading…</p>
      ) : steps && steps.length > 0 ? (
        <ol className="mb-2 space-y-1 text-sm">
          {steps.map((step) => (
            <li key={step.id} className="flex items-center gap-2">
              <span className="text-muted-foreground">#{step.step_order}</span>
              <Badge variant="outline">{step.channel}</Badge>
              <span className="truncate text-muted-foreground">{step.message_strategy}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mb-2 text-xs text-muted-foreground">No steps yet.</p>
      )}
      <form className="flex flex-wrap items-end gap-2" onSubmit={handleAdd}>
        <input
          className="h-8 w-32 rounded-md border border-input bg-background px-2 text-xs"
          onChange={(event) => setChannel(event.target.value)}
          placeholder="channel"
          value={channel}
        />
        <input
          className="h-8 w-56 rounded-md border border-input bg-background px-2 text-xs"
          onChange={(event) => setStrategy(event.target.value)}
          placeholder="message strategy"
          value={strategy}
        />
        <Button disabled={addStep.isPending} size="sm" type="submit" variant="outline">
          Add step #{nextOrder}
        </Button>
      </form>
    </div>
  );
}

function CampaignCard({
  campaign,
  onValidate,
  onPause,
  onResume,
  isValidating,
  isPausing,
  isResuming,
}: {
  campaign: Campaign;
  onValidate: () => void;
  onPause: () => void;
  onResume: () => void;
  isValidating: boolean;
  isPausing: boolean;
  isResuming: boolean;
}) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium">{campaign.name}</span>
              <Badge variant={STATUS_BADGE_VARIANT[campaign.status]}>{campaign.status}</Badge>
            </div>
            {campaign.objective ? (
              <p className="text-sm text-muted-foreground">{campaign.objective}</p>
            ) : null}
          </div>
          <div className="flex gap-2">
            {campaign.status === "DRAFT" && (
              <Button disabled={isValidating} onClick={onValidate} size="sm" variant="outline">
                Validate
              </Button>
            )}
            {campaign.status === "ACTIVE" && (
              <Button disabled={isPausing} onClick={onPause} size="sm" variant="outline">
                Pause
              </Button>
            )}
            {campaign.status === "PAUSED" && (
              <Button disabled={isResuming} onClick={onResume} size="sm" variant="outline">
                Resume
              </Button>
            )}
          </div>
        </div>
        <SequenceSteps campaignId={campaign.id} />
      </CardContent>
    </Card>
  );
}

/**
 * The Campaign engine's UI (CLAUDE.md §10.9, §10.10, §68 Milestone 14): create a draft,
 * validate it into an active campaign, pause/resume it, add/inspect its sequence steps — the
 * frontend half of the same lifecycle `tests/integration/test_campaign_engine.py` proves
 * against real Postgres.
 *
 * Real data end to end, through the typed `@colt/api-client` generated from the live OpenAPI
 * schema — but this page cannot be exercised live in this environment: there is no Keycloak
 * login flow here, so every request 401s with no real bearer token to attach. Type-checked
 * against the real schema is what's verified; a logged-in browser session is not.
 */
export function CampaignsPage() {
  const { data: campaigns, isLoading, isError } = useCampaigns();
  const createCampaign = useCreateCampaign();
  const validateCampaign = useValidateCampaign();
  const pauseCampaign = usePauseCampaign();
  const resumeCampaign = useResumeCampaign();

  const [name, setName] = useState("");
  const [objective, setObjective] = useState("");
  const [channels, setChannels] = useState("");

  const handleCreate = (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    createCampaign.mutate(
      {
        name: name.trim(),
        objective: objective.trim() || null,
        channels: channels
          .split(",")
          .map((channel) => channel.trim())
          .filter(Boolean),
      },
      {
        onSuccess: () => {
          setName("");
          setObjective("");
          setChannels("");
        },
      },
    );
  };

  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Target audiences, sequence steps, channels, and approvals for an outbound motion."
      />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>New campaign</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex flex-wrap items-end gap-3" onSubmit={handleCreate}>
            <label className="flex flex-col gap-1 text-sm">
              Name
              <input
                className="h-9 w-48 rounded-md border border-input bg-background px-3 text-sm"
                onChange={(event) => setName(event.target.value)}
                required
                value={name}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Objective
              <input
                className="h-9 w-56 rounded-md border border-input bg-background px-3 text-sm"
                onChange={(event) => setObjective(event.target.value)}
                value={objective}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Channels (comma-separated)
              <input
                className="h-9 w-56 rounded-md border border-input bg-background px-3 text-sm"
                onChange={(event) => setChannels(event.target.value)}
                placeholder="email, linkedin"
                value={channels}
              />
            </label>
            <Button disabled={createCampaign.isPending} type="submit">
              Create draft
            </Button>
          </form>
          <p className="mt-2 text-xs text-muted-foreground">
            A new campaign always starts as <code>DRAFT</code>. Set a target-audience definition,
            schedule and limits (via the API) before validating it — this form only covers what a
            quick draft needs.
          </p>
        </CardContent>
      </Card>

      {isLoading ? (
        <PageSkeleton />
      ) : isError ? (
        <EmptyState
          icon={Target}
          title="Could not load campaigns"
          description="The API request failed — in this environment, that's expected without a logged-in session (no Keycloak flow is wired up here)."
        />
      ) : campaigns && campaigns.length > 0 ? (
        <ul className="space-y-3">
          {campaigns.map((campaign) => (
            <li key={campaign.id}>
              <CampaignCard
                campaign={campaign}
                isPausing={pauseCampaign.isPending}
                isResuming={resumeCampaign.isPending}
                isValidating={validateCampaign.isPending}
                onPause={() => pauseCampaign.mutate(campaign.id)}
                onResume={() => resumeCampaign.mutate(campaign.id)}
                onValidate={() => validateCampaign.mutate(campaign.id)}
              />
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={Target}
          title="No campaigns yet"
          description="Create a draft above, then validate it once its targeting, channels, schedule and limits are set."
        />
      )}
    </div>
  );
}
