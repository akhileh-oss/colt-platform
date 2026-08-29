# Security model

> Skeleton established in Milestone 00; hardened and verified in Milestone 24. Specification:
> `CLAUDE.md` §26, §27, §33, §40, §41, §42.

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

## 3. Authorization

Capability-based permissions (`company:read`, `message:approve`, `campaign:launch`, …) over the
roles `OWNER`, `ADMIN`, `MANAGER`, `SALES`, `MARKETING`, `VIEWER`, `SERVICE_AGENT`
(`CLAUDE.md` §26.2).

## 4. Tenant isolation

Every tenant-owned query is organization-scoped. A client-supplied `organization_id` is never
trusted. PostgreSQL Row-Level Security is applied as defence in depth — it does not replace
application authorization. Cross-tenant isolation is proven by automated tests in `tests/security`
(`CLAUDE.md` §9.7, §27).

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
