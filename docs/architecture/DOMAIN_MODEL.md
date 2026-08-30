# Domain model

> Skeleton established in Milestone 00. `Organization` and `User` were built in Milestone 04
> (authentication + multi-tenancy needed a tenancy root and a principal to authenticate against).
> Milestone 05 built the rest of the core schema: `Company`, `Person`, `Signal`, `Evidence`,
> `Lead`, `Campaign`, `Message`, `Conversation`, `Opportunity` and `AuditLog`. The entities each
> feature milestone still owns (`LeadScore`, `SequenceStep`, `ConversationEvent`, `AgentRun`,
> `ToolCall`, `Approval`, `SuppressionEntry`) are built when that milestone needs them, not ahead
> of schedule. The authoritative field lists are `CLAUDE.md` §10 (and §48 for `AuditLog`); the
> state machines are §11.

## 1. Aggregates

| Entity            | Purpose                                                | Spec   | Status |
| ----------------- | ------------------------------------------------------ | ------ | ------ |
| Organization      | A Colt customer/workspace; the tenancy root            | §10.1  | ✅ M04 |
| User              | A person within an organization                        | §10.2  | ✅ M04 |
| Company           | A prospect company                                     | §10.3  | ✅ M05 |
| Person            | A contact at a company                                 | §10.4  | ✅ M05 |
| Signal            | A why-now event                                        | §10.5  | ✅ M05 |
| Evidence          | A sourced, dated, confidence-scored claim              | §10.6  | ✅ M05 |
| Lead              | A relationship-oriented prospect record                | §10.7  | ✅ M05 |
| LeadScore         | An append-only scoring evaluation                      | §10.8  |        |
| Campaign          | Targeting, sequence, channels, limits, approval policy | §10.9  | ✅ M05 |
| SequenceStep      | One step of a campaign sequence                        | §10.10 |        |
| Message           | A drafted or sent outbound message                     | §10.11 | ✅ M05 |
| Conversation      | A channel thread with a lead                           | §10.12 | ✅ M05 |
| ConversationEvent | An append-only conversation event                      | §10.13 |        |
| Opportunity       | A commercial opportunity                               | §10.14 | ✅ M05 |
| AgentRun          | One agent execution, fully attributed                  | §10.15 |        |
| ToolCall          | One tool invocation within an agent run                | §10.16 |        |
| Approval          | A human decision on a gated action                     | §10.17 |        |
| SuppressionEntry  | A global do-not-contact record                         | §10.18 |        |
| AuditLog          | An append-only record of a sensitive action            | §48    | ✅ M05 |

## 2. Tenancy

Every tenant-owned record carries `organization_id`. A client-supplied organization ID is never
trusted without cross-validation against the authenticated principal (`CLAUDE.md` §2.8, §27).

Enforced by two independent layers (Milestone 04,
[ADR-0005](../decisions/ADR-0005-auth-and-tenancy-architecture.md)):

1. **Application layer** — `colt_db.tenancy.TenantScopedRepository` is a base class that cannot
   construct a query without an `organization_id` filter; there is no method on it that queries
   unscoped.
2. **Database layer** — PostgreSQL Row-Level Security with `FORCE ROW LEVEL SECURITY`, keyed to a
   `SET LOCAL app.current_organization_id` session variable bound by `principal_provider` after
   JWT verification. The application connects as the restricted `colt_app` role rather than the
   Postgres superuser Alembic uses, since a superuser bypasses RLS unconditionally regardless of
   policy — the distinction this milestone's first real bug was found in.

The one legitimate unscoped lookup — resolving a verified JWT `sub` claim to a user, before an
organization is known — uses a narrow `app.bypass_rls` session flag, set only by
`SqlAlchemyUserDirectory.find_by_external_auth_id` and only after signature verification. Every
table Milestone 05 added carries `organization_id` and gets the same two-layer treatment — no
`app.bypass_rls` clause on any of them, since none has `users`' pre-organization-context lookup
problem. `tests/integration/test_domain_tables.py` asserts RLS is enabled, forced and policied on
all eleven tenant-owned tables by querying `pg_class`/`pg_policies` directly, so a future table
that forgets the policy fails a test rather than shipping silently unscoped.

## 3. State machines

Statuses are closed sets defined in `CLAUDE.md` §11 — lead state (§11.1), conversation state
(§11.2) and opportunity state (§11.3). Models may not invent statuses; transitions are made by
application code, not by model output.

`Organization` and `User` each carry a status of their own (`OrganizationStatus`:
ACTIVE/SUSPENDED/ARCHIVED; `UserStatus`, §10.2) — a suspended or archived organization, or an
inactive user, fails identity resolution identically to an unknown identity
(`ResolveOrganizationContext`), so a caller cannot distinguish "no such user" from "disabled user"
by probing.

## 4. Identity resolution

Layered matching, never fuzzy name similarity alone (`CLAUDE.md` §22).

`ResolveOrganizationContext` (Milestone 04) is the first instance of this pattern: it resolves a
verified external identity (`User.external_auth_id`, the Keycloak `sub` claim) to a `User` and
their `Organization`, and is the sole authority on organization membership and role — never the
identity provider, and never a client-supplied value.

## 5. Immutability

Score evaluations, conversation events, agent runs, tool calls and audit records are append-only.
History is never overwritten (`CLAUDE.md` §10.8, §9.4). `AuditLog` (Milestone 05) is the first
table this applies to: it has no `updated_at` column and its repository has no update method —
append-only is structural, not a convention someone has to remember. `Evidence` and `Signal`
(also Milestone 05) are append-only in the same sense: each row is one dated observation, so a
correction is a new row, not an edit to an old one.
