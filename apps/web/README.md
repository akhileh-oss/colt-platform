# @colt/web

The Colt operator console: Next.js App Router, React 19, Tailwind v4, and hand-written
shadcn/ui-style primitives (`CLAUDE.md` §3.1, §43).

```bash
make dev     # infrastructure
make api     # the API, on http://localhost:8000
make web     # this app, with reload, on http://localhost:3000
```

## Structure

See [`docs/architecture/ARCHITECTURE.md` §5](../../docs/architecture/ARCHITECTURE.md#5-frontend)
for the full layout and the Server/Client boundary rule. In short: `app/` is routing glue,
`features/<domain>/` is where page content actually lives, and a feature with no backend yet
renders an honest placeholder rather than fabricated data.

## Status

Every route in the primary nav renders. The dashboard's system health panel (real data from the
`/live`/`/ready` probes, Milestone 02) and the Campaigns page (Milestone 14 — create, validate,
pause, resume, list, and manage sequence steps, through the typed `@colt/api-client`) are
backed by real data; every
other panel and feature page is an explicit "not built yet," since there is no lead or message
data until their milestones land (15–22). The Campaigns page cannot be exercised in a live
browser session in this environment — there is no login flow yet, so every request 401s with no
real bearer token to attach — but it is type-checked against the real generated OpenAPI schema,
and the same request shapes are proven over HTTP by `apps/api/tests/test_colt_api_campaigns.py`.

## Commands

| Command                             | Does                                                                                |
| ----------------------------------- | ----------------------------------------------------------------------------------- |
| `pnpm --filter @colt/web dev`       | Dev server with reload                                                              |
| `pnpm --filter @colt/web build`     | Production build (also `make build`)                                                |
| `pnpm --filter @colt/web typecheck` | `tsc --noEmit`                                                                      |
| `make test-e2e`                     | Playwright, from the repo root — builds and starts both the API and this app itself |
