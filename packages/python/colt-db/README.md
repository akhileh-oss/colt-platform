# colt-db

SQLAlchemy models, repositories and Alembic migrations.

`SqlAlchemyCampaignRepository` (Milestone 14) gained `list_all()` and `update_status()` (the
same `cast(...).scalar_one()` → mutate → flush/refresh pattern `SqlAlchemyLeadRepository`'s own
`update_status()` established in Milestone 13), and `CampaignModel.status` now carries a
`CHECK` constraint against `colt_domain.CampaignStatus`'s five values — the same closed-
vocabulary-plus-database-constraint pattern `EvidenceModel.verification_status`/
`PersonModel.email_status` already use.

`sequence_steps` (CLAUDE.md §10.10, also Milestone 14) is a table this milestone's own Build
list names as its own deliverable, caught missing on review and added in the same PR: RLS-
enabled/forced with a `tenant_isolation` policy like every other tenant table, unique on
`(campaign_id, step_order)`, and the `messages.sequence_step_id` foreign key Milestone 05's own
`MessageModel` docstring promised this milestone would add — `ON DELETE SET NULL`, since a
message that was already sent must not disappear just because its step was later removed.
`colt_db.models` and `colt_db.repositories`' own `__init__.py` re-export lists also gained
`LeadScoreModel`/`SqlAlchemyLeadScoreRepository`, which Milestone 13 had defined but never
actually registered there — a second pre-existing gap this review caught in the same pass.

`approvals` and `suppression_entries` (CLAUDE.md §10.17-§10.18, Milestone 16) are new tables.
`approvals` is a plain tenant-owned table with the usual Row-Level Security. `suppression_
entries` is not plain: `organization_id` is nullable "for system-wide policy" (§10.18's own
words), so the usual `tenant_isolation` policy (`organization_id = current_setting(...)`) would
make a NULL-organization row invisible to every tenant — the opposite of what a system-wide
suppression is for. Its policy is `organization_id = current_setting(...) OR organization_id IS
NULL` instead, a deliberate, documented departure from every other tenant table's RLS policy in
this package. `SqlAlchemySuppressionRepository.is_suppressed()` likewise bypasses
`TenantScopedRepository._select_scoped()`'s strict equality filter, querying both an
organization's own entries and every global one.

`SqlAlchemyMessageRepository` (Milestone 16) gained `update_approval_status()`,
`update_send_result()`, and `count_sent_since()` — workflow-status mutators, not a reopening of
Milestone 15's append-only "versions" rule: that rule protects drafted _content_ from being
silently overwritten, not the lifecycle status of the one row a human or the policy engine is
actually deciding about.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
