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

Every route in the primary nav renders, and every panel is now backed by real data through the
typed `@colt/api-client`. The dashboard's system health panel (Milestone 02) reads the real
`/live`/`/ready` probes; every other dashboard panel (Milestone 22 — funnel, ICP performance,
trigger performance, message performance, channel performance, revenue outcomes, agent cost,
model performance) reads the Analytics + Learning Loop's REST surface. The Campaigns page
(Milestone 14 — create, validate, pause, resume, list, and manage sequence steps; Milestone 15
adds a list of each campaign's drafted messages; Milestone 16 makes the Approve/Reject buttons on
each `PENDING` message real) and the Opportunities page (Milestone 21 — pipeline summary, revenue
attribution, per-opportunity stage transition and owner assignment) are the other two real,
DB-backed pages. None of these pages can be exercised in a live browser session in this
environment — there is no login flow yet, so every request 401s with no real bearer token to
attach — but each is type-checked against the real generated OpenAPI schema, and the same request
shapes are proven over HTTP by the matching `apps/api` test module (e.g.
`apps/api/tests/test_colt_api_campaigns.py`).

## Commands

| Command                             | Does                                                                                |
| ----------------------------------- | ----------------------------------------------------------------------------------- |
| `pnpm --filter @colt/web dev`       | Dev server with reload                                                              |
| `pnpm --filter @colt/web build`     | Production build (also `make build`)                                                |
| `pnpm --filter @colt/web typecheck` | `tsc --noEmit`                                                                      |
| `make test-e2e`                     | Playwright, from the repo root — builds and starts both the API and this app itself |
