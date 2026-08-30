"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Catches a render error anywhere under the shell (CLAUDE.md §78: a meaningful error, not a
 * blank screen). Must be a client component — Next.js error boundaries only work as one.
 */
export default function ShellError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error in the app shell:", error);
  }, [error]);

  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
        <AlertTriangle aria-hidden="true" className="h-10 w-10 text-destructive" />
        <h2 className="text-base font-semibold">Something went wrong</h2>
        <p className="max-w-md text-sm text-muted-foreground">
          This page couldn't be displayed.
          {error.digest ? ` Reference: ${error.digest}` : ""}
        </p>
        <Button onClick={reset} variant="outline">
          Try again
        </Button>
      </CardContent>
    </Card>
  );
}
