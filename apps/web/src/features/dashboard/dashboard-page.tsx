import { PageHeader } from "@/components/page-header";

import { MetricCard } from "./metric-card";
import { SystemHealthPanel } from "./system-health-panel";

/**
 * The dashboard (CLAUDE.md §43.1). Every metric below "system health" reads "—" rather than a
 * fabricated number: there is no lead, campaign, or message data until their milestones land
 * (10–22), and this milestone's acceptance bar is the shell and a working API client, not a
 * populated control center.
 */
export function DashboardPage() {
  const metrics = [
    { label: "Prospects discovered", hint: "Milestone 11 — Discovery" },
    { label: "Qualified prospects", hint: "Milestone 13 — Lead scoring" },
    { label: "Research queue", hint: "Milestone 10 — Research" },
    { label: "Messages ready", hint: "Milestone 15 — Messaging" },
    { label: "Messages sent", hint: "Milestone 18 — Outreach workflow" },
    { label: "Positive replies", hint: "Milestone 19 — Reply intelligence" },
    { label: "Meetings", hint: "Milestone 19 — Reply intelligence" },
    { label: "Opportunities", hint: "Milestone 21 — Opportunity engine" },
  ] as const;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Revenue operations control center. Feature milestones populate each panel below."
      />

      <div className="mb-6">
        <SystemHealthPanel />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} label={metric.label} value="—" hint={metric.hint} />
        ))}
      </div>
    </div>
  );
}
