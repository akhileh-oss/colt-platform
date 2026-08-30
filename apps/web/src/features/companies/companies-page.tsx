import { Building2 } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

/** Prospect companies enriched from discovery and research. Placeholder until Milestone 11 — Discovery & enrichment lands (CLAUDE.md §68). */
export function CompaniesPage() {
  return (
    <div>
      <PageHeader title="Companies" />
      <EmptyState
        icon={Building2}
        title="Not built yet"
        description="Prospect companies enriched from discovery and research. This feature area arrives with Milestone 11 — Discovery & enrichment."
      />
    </div>
  );
}
