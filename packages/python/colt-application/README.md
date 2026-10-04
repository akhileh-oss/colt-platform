# colt-application

Use cases and application services coordinating domain objects and ports.

Ports (`colt_application.ports`) are `typing.Protocol`s, not `colt-db` imports — its concrete
repositories satisfy them structurally. `GetLead` is the use case `colt-agents`' `get_lead` tool
calls, realising `CLAUDE.md` §2.3's required path: Typed Tool → Application Service → Repository
→ PostgreSQL.

`colt_application.research.determine_verification_status()` is deterministic source-freshness
logic (CLAUDE.md §19.2, §2.1): it demotes a claim to `STALE` once its source is older than the
freshness threshold, but cannot promote one to `VERIFIED`/`DISPUTED`/`REJECTED` — those require
independent corroboration or human review, mechanisms a later milestone builds. `RecordEvidence`
is the one use case that writes an `Evidence` row (§10.6, §20); it computes
`verification_status` itself rather than trusting a caller-supplied value, since a tool argument
is attacker-adjacent model-decided input. `colt-agents`' `record_evidence` tool is the only
caller.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
