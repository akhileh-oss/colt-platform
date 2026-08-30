# ADR-0005 — Authentication, tenancy enforcement, and where Organization/User land

## Context

`CLAUDE.md` §68 sequences the milestones with Milestone 04 ("Authentication + Multi-Tenancy")
before Milestone 05 ("Database + Domain Foundation"). But M04's own build list includes
"organization model," "user model," and "tenant-scoped repositories," and M05's build list
separately includes "organizations" and "users" among the tables it creates. Authentication
cannot be verified without a subject to authenticate as; multi-tenancy cannot be verified without
a tenant to scope by and something to test isolation against. There is no way to satisfy M04's own
acceptance criteria — "organization context resolves," "cross-tenant access is denied" — without
some slice of the schema and a repository layer existing first.

Separately, §26 requires OIDC authentication with Keycloak locally, capability-based roles, and
service identities; §27 requires organization context resolved from authenticated identity, never
from a client-supplied value; §9.7 asks for PostgreSQL Row-Level Security as defense in depth,
with the application still responsible for the real enforcement. None of these pins an
implementation, and permission architecture, tenancy model, and data-storage architecture are all
explicit ADR triggers (§64).

## Decision

**Sequencing.** Milestone 04 builds `organizations` and `users` — the minimal slice needed to
authenticate a request and resolve its tenant — along with Alembic and the tenant-scoped
repository pattern. Milestone 05 extends the same migration chain with the remaining domain
tables (companies, people, signals, evidence, leads, campaigns, messages, conversations,
opportunities, audit logs) using the pattern this milestone establishes. This is read as
`CLAUDE.md` intends the ordering — M04 cannot be verified otherwise — not as a deviation from it.

**Layering.** Domain entities (`Organization`, `User`, `Role`) are pydantic models in
`colt-domain`, with no ORM or framework import — consistent with the ban already enforced by
`packages/python/colt-domain/ruff.toml`. `colt-application` defines repository ports as
`typing.Protocol`s. `colt-db` implements them with SQLAlchemy 2.x async, and owns Alembic. JWT
verification is boundary-layer authentication middleware, not a third-party "provider" in the
§28 sense (it authenticates requests to _our own_ API, it does not call out for business data),
so it lives directly in `colt-api`.

**Enforcement is two layers, and the layers do different jobs.** Tenant scoping is enforced
primarily by the application: a `TenantScopedRepository` base class is constructed with an
`organization_id` and structurally cannot run a query without filtering by it — there is no method
that accepts an unscoped query. PostgreSQL RLS is enabled on every tenant-owned table as defense in
depth (§9.7), keyed to a session-local setting (`app.current_organization_id`) set once per
request. RLS existing does not relax the repository requirement; a test suite proves each layer
independently, including a test that goes around the repository with raw SQL to confirm RLS still
blocks it.

**Authentication.** Keycloak (already running from Milestone 01, with the `colt` realm) issues
OIDC tokens against a proper client added in this milestone. Colt verifies bearer JWTs against
Keycloac's JWKS endpoint using `PyJWT`, and never stores or sees a password (§40: never store
plaintext passwords — Colt never receives one to store). Keycloak proves _who_ a request is;
it does not know about organizations. The `User` table, keyed by the token's `sub` claim
(`external_auth_id`), is the sole authority on which organization a subject belongs to and what
role they hold — organization membership is never encoded in or trusted from the token itself,
satisfying §27's "never trust organization_id from arbitrary [client-supplied] input" for the
identity token too, not only request bodies.

**Service identities** are a distinct principal type from human users (§26.3): a service token
authenticates as a named service (e.g. `colt-worker`), never impersonates a user, and is issued
its own capabilities rather than inheriting a role.

## Alternatives considered

**Wait for Milestone 05, stub authentication in M04.** Rejected: M04's stated acceptance criteria
— "user can authenticate," "cross-tenant access is denied" — cannot be genuinely satisfied by a
stub, and §0.4 forbids claiming a milestone complete without evidence.

**RLS only, no application-layer scoping.** Rejected. §9.7 is explicit that RLS is defense in
depth and "the application must still enforce authorization." Relying on RLS alone would mean a
raw query anywhere in the codebase that forgets to run under the right session setting fails
silent-open in a misconfigured session (RLS with `FORCE ROW LEVEL SECURITY` off, or a superuser
connection, bypasses it entirely) rather than fail-closed at the type level.

**Application-layer scoping only, no RLS.** Rejected. A single missed filter in a future query —
easy to introduce as the schema grows across Milestones 05–22 — would leak cross-tenant data with
no second layer to catch it. The cost of RLS (one migration-time policy per tenant-owned table) is
low relative to that risk.

**Store organization_id as a Keycloak custom claim, trust it from the token.** Rejected. It would
still be client-influenced in effect (whatever populates the claim), and it would let organization
membership drift between two systems of record. One system (`User`) stays authoritative.

**Roles and repository ports living in colt-db, no separate protocol layer.** Rejected: it would
mean `colt-application` depends on SQLAlchemy to type its own use cases, which is exactly the
inversion §5.2 rules out.

## Consequences

- Alembic, `make migrate`, `make migration`, and `make test-integration` — stubbed to Milestone 05
  since Milestone 00 — become real in this milestone instead, against the organizations/users
  slice. Milestone 05 extends the same chain; nothing here needs to be reworked when it does.
- Every future tenant-owned table needs both an application-layer scoped repository and an RLS
  policy. This is now the established pattern, not a per-table decision.
- A raw SQL escape hatch (a report query, a migration script) must explicitly set the session GUC
  or it is denied by RLS by default — annoying occasionally, safe always.
- `User.role` is a single enum value per organization membership in this milestone. Multiple
  organizations per human user, or per-resource permission overrides, are out of scope here and
  would need their own ADR if a future milestone requires them.

## Status

Accepted — 2026-08-30
