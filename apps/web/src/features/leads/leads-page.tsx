import { Users } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

/** Relationship-oriented prospect records, ICP score, evidence, and sequence state. Placeholder until Milestone 13 — Lead scoring & qualification lands (CLAUDE.md §68). */
export function LeadsPage() {
  return (
    <div>
      <PageHeader title="Leads" />
      <EmptyState
        icon={Users}
        title="Not built yet"
        description="Relationship-oriented prospect records, ICP score, evidence, and sequence state. This feature area arrives with Milestone 13 — Lead scoring & qualification."
      />
    </div>
  );
}
