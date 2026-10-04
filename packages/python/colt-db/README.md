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

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
