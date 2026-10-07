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

`conversation_events` (CLAUDE.md §10.13, Milestone 17) is a new table — append-only, no
`updated_at`, standard RLS (no departure needed, unlike `suppression_entries`). `event_metadata`
is this model's own column name for the domain entity's `metadata` field: `metadata` is reserved
on a Declarative model. `SqlAlchemyMessageRepository` gained `get_by_provider_message_id()` (how
an inbound reply resolves to the outbound `Message` it answers, §29.1) and `update_send_result()`
gained an optional `idempotency_key` parameter, claimed only at successful send time rather than
at draft time — see `colt-application`'s README for why. `SqlAlchemyConversationRepository`
(real since Milestone 05, but unused by any use case until now) gained `get_by_lead_and_channel()`,
`touch_last_activity()`, and `update_state()` — the last for `UnsubscribeByToken` terminating a
lead's open conversation.

`crm_sync_records` (CLAUDE.md §30, Milestone 20) is a new table — plain tenant-owned, standard
RLS, no departure needed. Unique on `(organization_id, entity_type, entity_id, provider_name)`,
backing `SqlAlchemyCrmSyncRecordRepository.get_by_target()`'s upsert lookup.
`SqlAlchemyOpportunityRepository.get()` (present since Milestone 05 but never read by a use case
until now) is this milestone's first real caller.

`opportunities.is_estimated_value` (CLAUDE.md §12.11, Milestone 21) is a new column — boolean,
`NOT NULL`, default `false` — labeling whether `estimated_value` came from a model's own
judgment rather than a configured source Colt trusts outright (§12.11: "estimates must be
labeled estimates"). `SqlAlchemyOpportunityRepository` gained `get_open_by_company()` (the
duplicate-creation check — one open, non-`WON`/`LOST` opportunity per company, oldest wins if
more than one somehow exists), `list_all()` (the pipeline dashboard's read model), and
`update_stage()`/`assign_owner()`/`update_value()` — the three real mutations; `.add()` gained
the new column as a keyword argument.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
