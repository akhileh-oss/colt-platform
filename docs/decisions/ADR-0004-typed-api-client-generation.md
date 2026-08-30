# ADR-0004 — Generate the TypeScript API client with openapi-typescript + openapi-fetch

## Context

`CLAUDE.md` §44 requires a typed TypeScript client generated from the FastAPI OpenAPI schema,
never hand-duplicated. It does not pick a tool, and several reasonable ones exist: a full
generated SDK (`openapi-generator-cli`, `orval`), or a types-only generator paired with a thin
typed fetch wrapper (`openapi-typescript` + `openapi-fetch`).

The client is consumed from `apps/web`, a Next.js App Router application using React Server
Components and Server Actions as well as client components. It must work identically in both.

## Decision

We generate **types only**, with `openapi-typescript`, from the OpenAPI schema exported directly
from the running `colt_api` application object — not from a live HTTP server. `apps/api` exposes a
`generate-openapi-schema` script that imports `colt_api.app:app` and writes `app.openapi()` to
`openapi.json` in-process. `pnpm --filter @colt/api-client generate` runs that script, then
`openapi-typescript` against the resulting file, into
`packages/typescript/api-client/src/generated/schema.d.ts`.

Requests are made with `openapi-fetch`, a ~6&nbsp;KB wrapper around `fetch` that types its
`get`/`post`/`patch`/`delete` calls entirely from that generated schema. `packages/typescript/api-client`
exports one configured client factory; nothing in `apps/web` constructs its own.

## Alternatives considered

**A fully generated SDK (`openapi-generator-cli`, `orval`).** These emit a function per operation
plus a bespoke runtime (interceptors, retry, sometimes a bundled HTTP client). Rejected: Colt
already owns retry, timeout and error-envelope handling as product requirements (`CLAUDE.md` §36,
§25.4), and a second runtime layered underneath would either duplicate that logic or fight it.
`openapi-fetch` is a types-only wrapper over the platform `fetch`, so Colt's own request logic
sits directly on top of it with nothing to reconcile.

**Hand-written fetch calls with hand-written types.** This is exactly what §44 forbids: contracts
drift the moment a Pydantic model changes, silently, because nothing fails until a wrong shape
reaches production.

**Generating from a live server instead of the app object.** Would require starting `colt_api`,
including its dependencies, as a step in every client regeneration and in CI, for a value the
`FastAPI` instance already computes in-process. Exporting `app.openapi()` directly needs nothing
running and is deterministic given the same source.

## Consequences

- Regenerating the client after an API change is `pnpm --filter @colt/api-client generate`,
  requiring nothing beyond the Python environment already needed to import `colt_api`.
- `src/generated/` is fully derived and is never hand-edited; the pre-existing rule that ESLint,
  Prettier and code review skip that directory already covers it.
- Server Components can call the same client the way any other async function is called; there is
  no framework-specific data-fetching layer to add on top.
- A future need for generated request/response validation, mocking, or contract testing can layer
  on `openapi-typescript`'s schema output without a rewrite, since the schema itself is the
  artifact, not one framework's interpretation of it.

## Status

Accepted — 2026-08-30
