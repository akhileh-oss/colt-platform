import { Settings } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

/** Organization, users, roles, and integration configuration. Placeholder until Milestone 04 — Authentication & multi-tenancy lands (CLAUDE.md §68). */
export function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" />
      <EmptyState
        icon={Settings}
        title="Not built yet"
        description="Organization, users, roles, and integration configuration. This feature area arrives with Milestone 04 — Authentication & multi-tenancy."
      />
    </div>
  );
}
