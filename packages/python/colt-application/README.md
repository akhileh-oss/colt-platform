# colt-application

Use cases and application services coordinating domain objects and ports.

Ports (`colt_application.ports`) are `typing.Protocol`s, not `colt-db` imports — its concrete
repositories satisfy them structurally. `GetLead` is the use case `colt-agents`' `get_lead` tool
calls, realising `CLAUDE.md` §2.3's required path: Typed Tool → Application Service → Repository
→ PostgreSQL.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
