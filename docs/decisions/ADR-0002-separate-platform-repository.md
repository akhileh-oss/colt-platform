# ADR-0002 — Build the platform in a repository separate from the marketing site

## Context

`akhileh-oss/colt-website` is the deployed Colt & Co marketing site: a Next.js 14 App Router
application with GSAP and three.js visuals, deployed on Vercel, carrying HubSpot and Meta CAPI lead
plumbing. Its release cadence is content-driven and its blast radius is a public web page.

The Colt platform specified in `CLAUDE.md` is a different system: a multi-tenant Python and
TypeScript monorepo with FastAPI, Temporal, PostgreSQL, Keycloak and object storage, whose blast
radius includes customer data and irreversible outbound side effects.

Placing both in one repository was considered because `CLAUDE.md` §4 specifies root-level files
(`Makefile`, `pyproject.toml`, `docker-compose.yml`, `pnpm-workspace.yaml`) that would collide with
the website's existing root, and because the website's Vercel build watches the repository root.

## Decision

We will build the Colt platform in a dedicated repository, `akhileh-oss/colt-platform`, laid out
exactly as `CLAUDE.md` §4 specifies. `akhileh-oss/colt-website` remains the marketing site and is
not restructured.

## Alternatives considered

**Convert `colt-website` into the monorepo**, moving the site under `apps/`. Most faithful to
§4's root layout, but it rewrites the paths of a live, deployed site and its Vercel configuration
for the benefit of a codebase that does not yet exist. The risk lands entirely on the working
system.

**Build the platform under a `platform/` subdirectory of `colt-website`.** Avoids touching the
site, but every root-level artefact §4 requires would sit one level down, so the specification and
the repository would disagree permanently. It also couples two systems with unrelated release
cadences and very different security postures into one set of branch protections and CI runs.

**Defer the decision and build nothing.** Rejected: the repository split is the cheapest decision
to make now and the most expensive to unwind later.

## Consequences

- The platform repository matches `CLAUDE.md` §4 exactly, with no path rewriting.
- The marketing site keeps its deployment, history and Vercel configuration untouched.
- Two repositories must be kept in view when Colt-branded work spans both. In practice they share
  almost nothing: the site markets the product, the platform is the product.
- If the marketing site later needs to consume platform APIs, it will do so as an external client
  over the published API, using the generated client — not through shared source.
- Should a single repository become genuinely desirable, merging two clean repositories is
  tractable; unpicking an entangled one is not.

## Status

Accepted — 2026-08-29
