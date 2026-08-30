# Security model

> Skeleton established in Milestone 00. Authentication, authorization and tenant isolation are
> real as of Milestone 04; the rest of this document is hardened and fully re-verified in
> Milestone 24. Specification: `CLAUDE.md` §26, §27, §33, §40, §41, §42.

## 1. Trust boundaries

| Boundary                 | Treatment                                             |
| ------------------------ | ----------------------------------------------------- |
| Browser → API            | Authenticated, authorized, rate-limited, size-limited |
| API → database           | Tenant-scoped, parameterized, RLS as defence in depth |
| Agent → tool             | Permission-filtered typed tools only                  |
| Tool → external provider | Policy-checked, adapter-mediated, idempotent          |
| External content → model | **Untrusted data, never instructions**                |

## 2. Authentication

OIDC/OAuth via an external identity provider — Keycloak locally, a managed provider in production,
behind the auth abstraction (`CLAUDE.md` §26.1). Background workers and agents use service
identities, never human credentials (§26.3).

Implemented in Milestone 04 (`colt_api.auth.JwtVerifier`,
[ADR-0005](../decisions/ADR-0005-auth-and-tenancy-architecture.md)): every protected route
verifies a bearer JWT's signature (via Keycloak's JWKS endpoint), issuer, audience and expiry
before anything else runs. The identity provider answers _who_ — the verified `sub` claim — and
nothing more. It is never asked, and never trusted, for _which organization_ or _what role_;
`ResolveOrganizationContext` looks those up from the `User` table, which is sole authority on
organization membership. An unknown identity and a suspended user fail identically
(`ApplicationError`/401), so neither can be distinguished by probing.

## 3. Authorization

Capability-based permissions (`company:read`, `message:approve`, `campaign:launch`, …) over the
roles `OWNER`, `ADMIN`, `MANAGER`, `SALES`, `MARKETING`, `VIEWER`, `SERVICE_AGENT`
(`CLAUDE.md` §26.2).

Implemented in Milestone 04 (`colt_domain.roles`): `DEFAULT_ROLE_PERMISSIONS` maps each role to
its permission set; `apps/api/src/colt_api/dependencies.py`'s `require_permission(Permission)`
dependency factory denies a request with 403 before the endpoint body runs if the resolved
principal's role lacks the required permission.

## 4. Tenant isolation

Every tenant-owned query is organization-scoped. A client-supplied `organization_id` is never
trusted. PostgreSQL Row-Level Security is applied as defence in depth — it does not replace
application authorization. Cross-tenant isolation is proven by automated tests in
`tests/integration/test_tenant_isolation.py` (the original `users` coverage from Milestone 04)
and `tests/integration/test_domain_tables.py` (the ten tables Milestone 05 added — `companies`,
`people`, `signals`, `evidence`, `leads`, `campaigns`, `messages`, `conversations`,
`opportunities`, `audit_logs`) (`CLAUDE.md` §9.7, §27); `tests/security` is populated once
Milestone 24 hardens and re-verifies the full surface.

Two independent layers enforce this (Milestone 04, extended to every table in Milestone 05),
detailed in [`docs/architecture/DOMAIN_MODEL.md`](../architecture/DOMAIN_MODEL.md#2-tenancy):
`TenantScopedRepository` at the application layer, and `FORCE ROW LEVEL SECURITY` policies keyed
to a per-session `app.current_organization_id` at the database layer. The database layer only
holds because the application connects as a restricted `colt_app` role rather than the Postgres
superuser Alembic uses for migrations — a Postgres superuser bypasses Row-Level Security
unconditionally, which would silently make every RLS policy in this repository dead code. This was
found, not assumed: an early integration test against the then-default (superuser) connection saw
every organization's rows from a session with no tenant context set.

## 5. Secrets

No secret is hard-coded, committed, logged, exposed to a frontend bundle, or returned through the
API. Local development uses git-ignored `.env`; production uses a managed secrets service
(`CLAUDE.md` §7.2).

`make security` enforces this on every tracked file via `scripts/check-secrets.sh`, which fails on
any finding absent from `.secrets.baseline`.

## 6. SSRF

Any URL-fetching feature resolves and validates destination IPs — blocking loopback, private,
link-local and cloud-metadata targets — and defends against DNS rebinding. Hostname validation
alone is insufficient. Redirects, response size and MIME type are bounded (`CLAUDE.md` §32, §33).

## 7. LLM-specific security

- Retrieved content is data; the model is told so explicitly (`CLAUDE.md` §41.1).
- Dangerous tools are not available while untrusted content is interpreted (§41.2).
- Data minimisation is applied before tool calls; tenant data and secrets are never exfiltrated to
  a provider outside an authorized operation (§41.3).
- Tool arguments and results never store secrets (`CLAUDE.md` §10.16).

## 8. Dependency and secret scanning

`make security` runs `pip-audit` (Python), `pnpm audit` (Node) and `detect-secrets` (working tree).
Wired in Milestone 00; enforced in CI in Milestone 26.

## 9. Outbound safety

Suppression is global within an organization and is checked immediately before every external send.
No campaign or agent may override it. Anti-abuse evasion and human impersonation are out of scope
by policy, not by omission (`CLAUDE.md` §18).
