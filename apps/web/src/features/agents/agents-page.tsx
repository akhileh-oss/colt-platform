import { Bot } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

/** Agent status, runs, latency, cost, and evaluation results. Placeholder until Milestone 09 — Agent runtime & tool registry lands (CLAUDE.md §68). */
export function AgentControlCenterPage() {
  return (
    <div>
      <PageHeader title="Agent control center" />
      <EmptyState
        icon={Bot}
        title="Not built yet"
        description="Agent status, runs, latency, cost, and evaluation results. This feature area arrives with Milestone 09 — Agent runtime & tool registry."
      />
    </div>
  );
}
