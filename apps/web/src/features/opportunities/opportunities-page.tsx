import { TrendingUp } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

/** Commercial opportunities created from qualified conversations. Placeholder until Milestone 21 — Opportunity engine lands (CLAUDE.md §68). */
export function OpportunitiesPage() {
  return (
    <div>
      <PageHeader title="Opportunities" />
      <EmptyState
        icon={TrendingUp}
        title="Not built yet"
        description="Commercial opportunities created from qualified conversations. This feature area arrives with Milestone 21 — Opportunity engine."
      />
    </div>
  );
}
