import { createColtClient, type ColtClient } from "@colt/api-client";

import { config } from "@/lib/config";

/**
 * The shared client instance for client components. Server Components should call
 * `createColtClient` directly with a request-scoped ID instead of importing this (CLAUDE.md
 * §5.1: dependency injection, not a module-level singleton smuggling per-request state).
 */
export const apiClient: ColtClient = createColtClient({ baseUrl: config.apiBaseUrl });
