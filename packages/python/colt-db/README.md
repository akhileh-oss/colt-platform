# colt-db

SQLAlchemy models, repositories and Alembic migrations.

`SqlAlchemyCampaignRepository` (Milestone 14) gained `list_all()` and `update_status()` (the
same `cast(...).scalar_one()` → mutate → flush/refresh pattern `SqlAlchemyLeadRepository`'s own
`update_status()` established in Milestone 13), and `CampaignModel.status` now carries a
`CHECK` constraint against `colt_domain.CampaignStatus`'s five values — the same closed-
vocabulary-plus-database-constraint pattern `EvidenceModel.verification_status`/
`PersonModel.email_status` already use.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
