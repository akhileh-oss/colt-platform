"use client";

import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

import { useSystemHealth } from "@/hooks/use-system-health";
import { cn } from "@/lib/utils";

/**
 * A small always-visible indicator, not just the dashboard panel: an operator should be able
 * to tell the platform is unhealthy from anywhere in the console (CLAUDE.md §43.1).
 */
export function SystemHealthBadge() {
  const { data, isLoading, isError } = useSystemHealth();

  if (isLoading) {
    return (
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 aria-hidden="true" className="h-3.5 w-3.5 animate-spin" />
        Checking system health
      </span>
    );
  }

  const healthy = !isError && data?.live && data?.ready;

  return (
    <span
      className={cn(
        "flex items-center gap-1.5 text-xs font-medium",
        healthy ? "text-success" : "text-destructive",
      )}
    >
      {healthy ? (
        <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
      ) : (
        <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />
      )}
      <span aria-live="polite">{healthy ? "All systems healthy" : "System health degraded"}</span>
    </span>
  );
}
