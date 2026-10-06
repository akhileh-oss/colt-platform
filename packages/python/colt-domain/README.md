# colt-domain

Entities, value objects, enumerations, invariants and deterministic business rules.

`Approval` (§10.17) and `SuppressionEntry` (§10.18, Milestone 16) are the newest additions.
`Approval.status` is a closed `ApprovalStatus` enum (`PENDING`/`APPROVED`/`REJECTED`) by the
same reasoning §11's "do not let LLMs invent arbitrary statuses" applies to any deterministically
checked status, not only the three entities §11 numbers. `SuppressionEntry.organization_id` is
nullable "for system-wide policy," per §10.18's own field listing — not a guess left unstated.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
