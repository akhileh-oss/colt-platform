/**
 * The typed Colt API client (CLAUDE.md §44).
 *
 * `paths` comes from `generated/schema.d.ts`, produced from the FastAPI OpenAPI schema and
 * never hand-edited (see ADR-0004). `openapi-fetch` types every method, path, query, and
 * request/response body from that schema — a route that does not exist, or a body shape that
 * does not match, is a compile error here rather than a runtime surprise.
 */

import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./generated/schema";

export interface CreateColtClientOptions {
  /** Origin the client talks to, e.g. `http://localhost:8000`. No trailing slash. */
  baseUrl: string;
  /** Called before each request; return a header value or `undefined` to omit it. */
  getRequestId?: () => string | undefined;
}

/**
 * Build a configured client. One instance per request context in a server environment;
 * a single shared instance is fine in the browser (CLAUDE.md §5.1: dependency injection,
 * not a module-level singleton smuggling per-request state).
 */
export function createColtClient(options: CreateColtClientOptions) {
  const client = createClient<paths>({ baseUrl: options.baseUrl });

  if (options.getRequestId) {
    const requestIdMiddleware: Middleware = {
      onRequest({ request }) {
        const requestId = options.getRequestId?.();
        if (requestId) {
          request.headers.set("X-Request-ID", requestId);
        }
        return request;
      },
    };
    client.use(requestIdMiddleware);
  }

  return client;
}

export type ColtClient = ReturnType<typeof createColtClient>;
