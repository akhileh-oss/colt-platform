# Architecture

> Skeleton established in Milestone 00. Sections are filled in as the milestones that build each
> layer land. `CLAUDE.md` remains the authoritative specification — this document explains **how
> the code actually realises it**, and must be updated whenever behaviour changes (`CLAUDE.md` §63).

## 1. System shape

Colt is a deterministic platform with AI reasoning components. Responsibilities are separated
absolutely (`CLAUDE.md` §2.1):

| Concern                              | Owner                         |
| ------------------------------------ | ----------------------------- |
| Reasoning                            | Claude, via the agent runtime |
| Controlled capabilities              | Typed tool registry           |
| Authorization and business safety    | Policy engine                 |
| Deterministic business logic         | Application services          |
| Business source of truth             | PostgreSQL                    |
| Durable orchestration                | Temporal                      |
| Cache, locks, ephemeral coordination | Redis                         |
| API boundary                         | FastAPI                       |
| Presentation                         | Next.js                       |

## 2. Layering

Dependencies point inward:

```text
Presentation → API/UI → Application → Domain → Ports → Infrastructure
```

The domain layer imports no framework, ORM, SDK or provider module (`CLAUDE.md` §5.3).

Two mechanisms carry this, and it is worth being precise about what each does. The workspace
dependency graph in each `pyproject.toml` **declares** the shape — it is the documentation of
intent — but it does not enforce it: `uv` installs every workspace package into a single shared
virtualenv, so at runtime any package can import anything present. Enforcement therefore comes
from `packages/python/colt-domain/ruff.toml`, which bans the forbidden modules outright via
`flake8-tidy-imports`. A forbidden import in the domain fails `make lint`, whether or not it is
used.

## 3. Package map

| Package              | Layer          | Responsibility                                                                    |
| -------------------- | -------------- | --------------------------------------------------------------------------------- |
| `colt-domain`        | Domain         | Entities, value objects, invariants, deterministic rules                          |
| `colt-application`   | Application    | Use cases, orchestration of domain objects and ports                              |
| `colt-policy`        | Application    | Authorization and business-safety decisions                                       |
| `colt-db`            | Infrastructure | SQLAlchemy models, repositories, migrations                                       |
| `colt-integrations`  | Infrastructure | Provider adapters behind domain-facing ports                                      |
| `colt-ai`            | Infrastructure | AI gateway: model routing, usage and cost accounting                              |
| `colt-agents`        | Application    | Agent definitions, prompts, runtime integration                                   |
| `colt-workflows`     | Application    | Temporal workflows and activities                                                 |
| `colt-observability` | Cross-cutting  | Logging, tracing, metrics                                                         |
| `colt-config`        | Cross-cutting  | Typed settings — see [ADR-0003](../decisions/ADR-0003-shared-settings-package.md) |
| `colt-api`           | Presentation   | FastAPI routers, DTOs, composition root                                           |

## 4. Request path

```text
client
  → RequestContextMiddleware      assign/validate X-Request-ID, bind log context
  → AccessLogMiddleware           one structured line per request
  → CORSMiddleware                origin allow-list
  → SecurityHeadersMiddleware     nosniff, DENY, no-referrer, COOP, Permissions-Policy
  → RequestSizeLimitMiddleware    reject oversized bodies
  → router (/api/v1 or probes)
  → dependency injection          settings today; principal and session in 04 and 05
  → endpoint
```

Middleware is registered in reverse: the request context is added last so it is outermost and
every inner layer can read the request ID.

Failures leave through the handlers in `colt_api.errors`, which render the single §25.4 envelope.
The handler for an unhandled `Exception` runs inside Starlette's `ServerErrorMiddleware`, outside
our stack, so it resolves the request ID from the request scope rather than the logging context —
otherwise 500s, the responses that most need tracing, would carry no ID.

Readiness is a registry (`colt_api.readiness`) rather than a fixed list, so Milestone 05 adds the
database check and Milestone 06 Temporal with one call each.

## 5. Frontend

`apps/web` is a Next.js App Router application under `src/`, laid out per `CLAUDE.md` §43:

```text
apps/web/src/
  app/                  routes, layouts, error/loading/not-found boundaries
  features/<domain>/    per-feature page content (dashboard, leads, campaigns, ...)
  components/           shared shell and UI primitives
  lib/                  cn(), runtime config, the TanStack Query client factory
  hooks/                shared client hooks (e.g. useSystemHealth)
  api/                  the configured @colt/api-client instance
  styles/               globals.css and design tokens
```

`app/` stays thin — routing and metadata only. Page content lives in `features/<domain>/`, which
each route's `page.tsx` imports and renders. A feature with no backend yet (every one except the
probes, until Milestone 10 onward) renders an honest `EmptyState` naming the milestone that
populates it, rather than fabricated data (`CLAUDE.md` §0.4).

### Server/Client boundary

`app/(shell)/layout.tsx` wraps every product route in `AppShell` — sidebar, header, live system
health. Interactive pieces (`NavLink`, `SystemHealthBadge`) are Client Components; everything else
renders on the server by default.

One constraint bit us building this: React Server Components serialise the whole rendered tree
for the RSC payload (needed for client-side navigation), and a raw component reference is not a
serialisable value the moment it crosses into a Client Component's props — only a rendered
element is. `NAV_ITEMS` therefore stores icon _components_, but `AppShell` (Server) renders each
one to an element — `<item.icon ... />` — before handing it to `NavLink` (Client) as a prop. Passing
the bare component reference instead fails the production build with "Functions cannot be passed
directly to Client Components," only at build/prerender time, not in `next dev`.

### Data fetching

Server state goes through TanStack Query (`CLAUDE.md` §77) via the client in `src/api/client.ts`
for Client Components; Server Components should construct their own request-scoped client with
`createColtClient` rather than importing that shared instance (`CLAUDE.md` §5.1). No global store
mirrors backend state.

### API client

`@colt/api-client` is generated from the FastAPI OpenAPI schema — see
[ADR-0004](../decisions/ADR-0004-typed-api-client-generation.md) and
[`packages/typescript/api-client/README.md`](../../packages/typescript/api-client/README.md).
`pnpm --filter @colt/api-client generate` (or `make api-client`) regenerates it; the output is
committed so a fresh checkout typechecks without running Python first.

## 6. Data flow: the core product loop

_To be documented as Milestones 10–22 land. The loop is specified in `CLAUDE.md` §1.3._

## 7. Deployment topology

_To be documented in Milestone 25._
