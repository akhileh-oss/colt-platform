"use client";

import { PageHeader, PageSkeleton } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useAgentCost,
  useChannelPerformance,
  useFunnel,
  useIcpPerformance,
  useMessagePerformance,
  useModelPerformance,
  useRevenueOutcomes,
  useTriggerPerformance,
} from "@/hooks/use-analytics";

import { SystemHealthPanel } from "./system-health-panel";

function pct(value: number): string {
  return `${(value * 100).toLocaleString(undefined, { maximumFractionDigits: 0 })}%`;
}

function num(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function FunnelPanel() {
  const { data: stages, isLoading } = useFunnel();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Funnel</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !stages || stages.length === 0 ? (
          <p className="text-sm text-muted-foreground">No leads yet.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
            {stages.map((stage) => (
              <div className="rounded-lg border border-border p-3" key={stage.status}>
                <p className="text-xs text-muted-foreground">{stage.status}</p>
                <p className="mt-1 text-xl font-semibold tabular-nums">{num(stage.count)}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function IcpPerformancePanel() {
  const { data: rows, isLoading } = useIcpPerformance();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>ICP performance</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !rows || rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No companies yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1">Industry</th>
                <th className="py-1 text-right">Companies</th>
                <th className="py-1 text-right">Leads</th>
                <th className="py-1 text-right">Qualified leads</th>
                <th className="py-1 text-right">Won companies</th>
                <th className="py-1 text-right">Won revenue</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="border-t border-border" key={row.industry}>
                  <td className="py-1.5">{row.industry}</td>
                  <td className="py-1.5 text-right">{num(row.company_count)}</td>
                  <td className="py-1.5 text-right">{num(row.lead_count)}</td>
                  <td className="py-1.5 text-right">{num(row.qualified_lead_count)}</td>
                  <td className="py-1.5 text-right">{num(row.won_company_count)}</td>
                  <td className="py-1.5 text-right">{num(row.won_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function TriggerPerformancePanel() {
  const { data: rows, isLoading } = useTriggerPerformance();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Trigger performance</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !rows || rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No signals yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1">Signal type</th>
                <th className="py-1 text-right">Signals</th>
                <th className="py-1 text-right">Companies</th>
                <th className="py-1 text-right">Won companies</th>
                <th className="py-1 text-right">Avg confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="border-t border-border" key={row.signal_type}>
                  <td className="py-1.5">{row.signal_type}</td>
                  <td className="py-1.5 text-right">{num(row.signal_count)}</td>
                  <td className="py-1.5 text-right">{num(row.company_count)}</td>
                  <td className="py-1.5 text-right">{num(row.won_company_count)}</td>
                  <td className="py-1.5 text-right">
                    {row.average_confidence != null ? pct(row.average_confidence) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function MessagePerformancePanel() {
  const { data: rows, isLoading } = useMessagePerformance();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Message performance</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !rows || rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No messages yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1">Prompt version</th>
                <th className="py-1">Persona</th>
                <th className="py-1 text-right">Drafted</th>
                <th className="py-1 text-right">Sent</th>
                <th className="py-1 text-right">Approved</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="border-t border-border" key={`${row.prompt_version}-${row.persona}`}>
                  <td className="py-1.5">{row.prompt_version}</td>
                  <td className="py-1.5">{row.persona}</td>
                  <td className="py-1.5 text-right">{num(row.drafted_count)}</td>
                  <td className="py-1.5 text-right">{num(row.sent_count)}</td>
                  <td className="py-1.5 text-right">{num(row.approved_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function ChannelPerformancePanel() {
  const { data: rows, isLoading } = useChannelPerformance();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Channel performance</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !rows || rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No channel activity yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1">Channel</th>
                <th className="py-1 text-right">Messages</th>
                <th className="py-1 text-right">Sent</th>
                <th className="py-1 text-right">Conversations</th>
                <th className="py-1 text-right">Positive</th>
                <th className="py-1 text-right">Positive rate</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="border-t border-border" key={row.channel}>
                  <td className="py-1.5">{row.channel}</td>
                  <td className="py-1.5 text-right">{num(row.message_count)}</td>
                  <td className="py-1.5 text-right">{num(row.sent_count)}</td>
                  <td className="py-1.5 text-right">{num(row.conversation_count)}</td>
                  <td className="py-1.5 text-right">{num(row.positive_count)}</td>
                  <td className="py-1.5 text-right">{pct(row.positive_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function AgentCostPanel() {
  const { data: rows, isLoading } = useAgentCost();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Agent cost</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !rows || rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No agent runs yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1">Agent</th>
                <th className="py-1 text-right">Runs</th>
                <th className="py-1 text-right">Cost (USD)</th>
                <th className="py-1 text-right">Input tokens</th>
                <th className="py-1 text-right">Output tokens</th>
                <th className="py-1 text-right">Tool tokens</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="border-t border-border" key={row.agent_name}>
                  <td className="py-1.5">{row.agent_name}</td>
                  <td className="py-1.5 text-right">{num(row.run_count)}</td>
                  <td className="py-1.5 text-right">
                    {row.total_cost_usd.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 4,
                    })}
                  </td>
                  <td className="py-1.5 text-right">{num(row.total_input_tokens)}</td>
                  <td className="py-1.5 text-right">{num(row.total_output_tokens)}</td>
                  <td className="py-1.5 text-right">{num(row.total_tool_tokens)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function ModelPerformancePanel() {
  const { data: rows, isLoading } = useModelPerformance();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Model performance</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !rows || rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No agent runs yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="py-1">Model</th>
                <th className="py-1 text-right">Runs</th>
                <th className="py-1 text-right">Completed</th>
                <th className="py-1 text-right">Failed</th>
                <th className="py-1 text-right">Success rate</th>
                <th className="py-1 text-right">Avg cost (USD)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="border-t border-border" key={row.model_name}>
                  <td className="py-1.5">{row.model_name}</td>
                  <td className="py-1.5 text-right">{num(row.run_count)}</td>
                  <td className="py-1.5 text-right">{num(row.completed_count)}</td>
                  <td className="py-1.5 text-right">{num(row.failed_count)}</td>
                  <td className="py-1.5 text-right">{pct(row.success_rate)}</td>
                  <td className="py-1.5 text-right">
                    {row.average_cost_usd != null
                      ? row.average_cost_usd.toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 4,
                        })
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function RevenueOutcomesPanel() {
  const { data: rows, isLoading } = useRevenueOutcomes();

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Revenue outcomes</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <PageSkeleton />
        ) : !rows || rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No closed-won revenue yet.</p>
        ) : (
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
                    {num(row.total_value)}
                    {row.includes_estimate ? (
                      <span className="ml-1 text-xs text-muted-foreground">(incl. estimate)</span>
                    ) : null}
                  </td>
                  <td className="py-1.5 text-right">{num(row.opportunity_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * The dashboard (CLAUDE.md §43.1, Milestone 22's "dashboard can answer what segments, signals,
 * personas, channels and message variants produce commercial outcomes"). Every panel below
 * "system health" is now real data from the Analytics + Learning Loop REST surface, typed
 * end-to-end from the generated OpenAPI schema — funnel, ICP (segment) performance, trigger
 * (signal) performance, message (variant/persona) performance, channel performance, agent cost,
 * model performance, and revenue outcomes.
 */
export function DashboardPage() {
  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Revenue operations control center — funnel, segment, signal, persona, channel, and cost analytics."
      />

      <div className="mb-6">
        <SystemHealthPanel />
      </div>

      <FunnelPanel />
      <IcpPerformancePanel />
      <TriggerPerformancePanel />
      <MessagePerformancePanel />
      <ChannelPerformancePanel />
      <RevenueOutcomesPanel />
      <AgentCostPanel />
      <ModelPerformancePanel />
    </div>
  );
}
