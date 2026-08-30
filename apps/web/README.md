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

Every route in the primary nav renders. Only the dashboard's system health panel is backed by
real data (the `/live` and `/ready` probes from Milestone 02) — every other panel and every other
feature page is an explicit "not built yet," since there is no lead, campaign, or message data
until their milestones land (10–22).

## Commands

| Command                             | Does                                                                                |
| ----------------------------------- | ----------------------------------------------------------------------------------- |
| `pnpm --filter @colt/web dev`       | Dev server with reload                                                              |
| `pnpm --filter @colt/web build`     | Production build (also `make build`)                                                |
| `pnpm --filter @colt/web typecheck` | `tsc --noEmit`                                                                      |
| `make test-e2e`                     | Playwright, from the repo root — builds and starts both the API and this app itself |
