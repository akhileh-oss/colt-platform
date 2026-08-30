# @colt/api-client

Typed client for the Colt API, generated from the FastAPI OpenAPI schema (`CLAUDE.md` §44,
[ADR-0004](../../../docs/decisions/ADR-0004-typed-api-client-generation.md)).

```bash
pnpm --filter @colt/api-client generate   # regenerate after any API change
```

That runs two steps: `generate:schema` exports `colt_api`'s OpenAPI schema in-process (no server
needed) to `openapi.json`, then `generate:types` runs `openapi-typescript` against it into
`src/generated/schema.d.ts`. **Never edit `src/generated/` by hand** — it is overwritten on every
run.

```typescript
import { createColtClient, isColtErrorResponse } from "@colt/api-client";

const client = createColtClient({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL! });

const { data, error } = await client.GET("/api/v1/meta");
if (error) {
  // `error` is typed from the schema for this exact route.
}
```

Every route, method, query parameter, and request/response body is typed from the schema — call
a route that does not exist, or send a body of the wrong shape, and it fails to compile.

`isColtErrorResponse` narrows an unknown failure value to the shared `{ error: { code, message,
request_id, details } }` envelope (`CLAUDE.md` §25.4) so callers can branch on `error.code` from
the same closed set the backend uses (`CLAUDE.md` §36).
