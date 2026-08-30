"use client";

import { CheckCircle2, XCircle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSystemHealth } from "@/hooks/use-system-health";

/**
 * The dashboard's "system health" panel (CLAUDE.md §43.1), driven by the real `/live` and
 * `/ready` probes built in Milestone 02 — the one dashboard panel with genuine data behind it
 * at this milestone.
 */
export function SystemHealthPanel() {
  const { data, isLoading, isError } = useSystemHealth();

  return (
    <Card>
      <CardHeader>
        <CardTitle>System health</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Checking...</p>
        ) : isError ? (
          <p className="flex items-center gap-2 text-sm text-destructive">
            <XCircle aria-hidden="true" className="h-4 w-4" />
            Could not reach the API.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            <li className="flex items-center gap-2">
              {data?.live ? (
                <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-success" />
              ) : (
                <XCircle aria-hidden="true" className="h-4 w-4 text-destructive" />
              )}
              API process {data?.live ? "alive" : "unreachable"}
            </li>
            <li className="flex items-center gap-2">
              {data?.ready ? (
                <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-success" />
              ) : (
                <XCircle aria-hidden="true" className="h-4 w-4 text-destructive" />
              )}
              API ready to accept work
            </li>
            {Object.entries(data?.checks ?? {}).map(([name, check]) => (
              <li key={name} className="flex items-center gap-2 pl-6 text-muted-foreground">
                {check.ready ? (
                  <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5 text-success" />
                ) : (
                  <XCircle aria-hidden="true" className="h-3.5 w-3.5 text-destructive" />
                )}
                {name}
                {check.detail ? `: ${check.detail}` : ""}
              </li>
            ))}
            {Object.keys(data?.checks ?? {}).length === 0 && (
              <li className="pl-6 text-xs text-muted-foreground">
                No dependency checks registered yet — the database and Temporal checks land in
                Milestones 05 and 06.
              </li>
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
