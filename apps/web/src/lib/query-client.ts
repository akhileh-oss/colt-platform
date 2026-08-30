import { QueryClient } from "@tanstack/react-query";

/**
 * One `QueryClient` per request on the server, one shared instance in the browser — the
 * standard TanStack Query App Router pattern, so server-rendered and client-fetched data never
 * leak across requests.
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // A network blip should not immediately read as "this feature is broken."
        retry: 1,
        staleTime: 30_000,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

export function getQueryClient(): QueryClient {
  if (typeof window === "undefined") {
    return makeQueryClient();
  }
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}
