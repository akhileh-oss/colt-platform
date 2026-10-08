# colt-domain

Entities, value objects, enumerations, invariants and deterministic business rules.

`Approval` (§10.17) and `SuppressionEntry` (§10.18, Milestone 16) are the newest additions.
`Approval.status` is a closed `ApprovalStatus` enum (`PENDING`/`APPROVED`/`REJECTED`) by the
same reasoning §11's "do not let LLMs invent arbitrary statuses" applies to any deterministically
checked status, not only the three entities §11 numbers. `SuppressionEntry.organization_id` is
nullable "for system-wide policy," per §10.18's own field listing — not a guess left unstated.

`CrmSyncRecord` (§30, Milestone 20) is a new polymorphic entity (`entity_type` + `entity_id`,
the same reasoning `Evidence` already establishes), not a column on `Company`/`Person`/
`Opportunity` — it tracks how one Colt entity maps to one external CRM provider's object. Unique
on `(organization_id, entity_type, entity_id, provider_name)`, enabling idempotent upsert
semantics. `sync_status` is a milestone-invented closed `SyncStatus` enum
(`PENDING`/`SYNCED`/`FAILED`) — CLAUDE.md names the field without enumerating values, the same
documented-design-decision pattern `CampaignStatus`/`Urgency` already establish. `.synced()`/
`.failed()` are the same `model_copy`-returning helper-method shape `Lead.with_status()`/
`Conversation.with_state()` already use.

`Opportunity.is_estimated_value` (§12.11, Milestone 21) labels whether `estimated_value` came
from a model's own judgment rather than a configured source — §12.11's "estimates must be
labeled estimates" needs somewhere to record that distinction. `.with_owner()`/`.with_value()`
join `.with_stage()` as the entity's mutation helpers, the same `model_copy`-returning shape as
every other entity's own.

`Campaign.name`, `Company.name`, `Person.full_name` (CLAUDE.md §40, Milestone 24) now reject a
value past 300 characters, and `Message.subject` past 500 — each a `pydantic.Field(max_length=
...)` matching its backing `colt_db` model's own `String(N)` column width exactly, so this layer
never claims a looser bound than PostgreSQL actually enforces. `Company.description` and
`Message.body` back onto unbounded `Text` columns with no DB-side cap to match, so they get
their own deliberately tighter, documented caps instead (5,000 and 100,000 characters) —
generous enough for any real use, never unbounded.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
