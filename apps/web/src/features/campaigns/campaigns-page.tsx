import { Target } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

/** ICP definition, sequence, channels, approvals, and outcomes. Placeholder until Milestone 14 — Campaign engine lands (CLAUDE.md §68). */
export function CampaignsPage() {
  return (
    <div>
      <PageHeader title="Campaigns" />
      <EmptyState
        icon={Target}
        title="Not built yet"
        description="ICP definition, sequence, channels, approvals, and outcomes. This feature area arrives with Milestone 14 — Campaign engine."
      />
    </div>
  );
}
