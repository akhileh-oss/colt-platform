import { MessageSquare } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

/** Inbound and outbound threads, classified by reply intelligence. Placeholder until Milestone 19 — Reply intelligence lands (CLAUDE.md §68). */
export function ConversationsPage() {
  return (
    <div>
      <PageHeader title="Conversations" />
      <EmptyState
        icon={MessageSquare}
        title="Not built yet"
        description="Inbound and outbound threads, classified by reply intelligence. This feature area arrives with Milestone 19 — Reply intelligence."
      />
    </div>
  );
}
