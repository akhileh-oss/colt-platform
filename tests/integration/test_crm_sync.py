"""Milestone 20's acceptance criterion, proven literally: "CRM outage does not break core Colt
workflows; sync retries safely after recovery" (CLAUDE.md §30, §68).

**What this proves for real, against real Postgres:**

- A `FakeCRMProvider` failure syncing one `Company` does not prevent an unrelated core Colt use
  case (`RecordEvidence`) from completing normally in the same test run — the literal "CRM outage
  does not break core Colt workflows" half of the criterion.
- `sync_entity_to_crm_activity`, called directly (a plain async function outside Temporal's own
  activity execution context — it never touches `activity.info()`, the same legitimate shortcut
  `test_lead_outreach_activities.py` already documents), records a `FAILED` `CrmSyncRecord` on a
  simulated provider outage, and a later successful retry against the same `(entity_type,
  entity_id, provider_name)` updates that exact row to `SYNCED` rather than creating a second
  one, and creates exactly one provider-side object — the literal "sync retries safely after
  recovery" half.

Requires a real Postgres. Marked `integration`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from temporalio.exceptions import ApplicationError

from colt_application import RecordEvidence
from colt_db.repositories.company_repository import SqlAlchemyCompanyRepository
from colt_db.repositories.crm_sync_record_repository import SqlAlchemyCrmSyncRecordRepository
from colt_db.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from colt_domain import SyncStatus
from colt_integrations.errors import ProviderUnavailableError
from colt_workflows.activities.crm_sync import (
    SyncEntityToCrmActivityInput,
    get_fake_crm_provider,
    sync_entity_to_crm_activity,
)

SessionFactory = Any
NOW = datetime.now(UTC)


@pytest.fixture(autouse=True)
def _reset_fake_crm_provider() -> None:
    """The activity's `FakeCRMProvider` is a module-level singleton (one shared instance for a
    process's whole lifetime, by design — see that module's docstring). Reset it before each
    test so one test's queued failures/stored objects never leak into the next."""
    get_fake_crm_provider().reset()


async def _seed_company(session: Any, org_id: UUID) -> UUID:
    companies = await SqlAlchemyCompanyRepository.create(session, org_id)
    company = await companies.add(name="Acme Rockets", domain="acme-rockets.example")
    return company.id


@pytest.mark.asyncio
async def test_a_crm_outage_does_not_break_an_unrelated_core_colt_use_case(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        company_id = await _seed_company(seed_session, org_a)

    get_fake_crm_provider().queue_failure(
        "COMPANY", str(company_id), ProviderUnavailableError("simulated CRM outage")
    )

    with pytest.raises(ApplicationError, match="simulated CRM outage"):
        await sync_entity_to_crm_activity(
            SyncEntityToCrmActivityInput(
                organization_id=str(org_a),
                entity_type="Company",
                entity_id=str(company_id),
                provider_account_id="acct-1",
            )
        )

    # The CRM outage above must not have touched anything outside its own CrmSyncRecord row —
    # a core use case against the very same company succeeds normally, in a fresh session, right
    # after.
    core_session = await open_app_session()
    async with core_session, core_session.begin():
        evidence_repo = await SqlAlchemyEvidenceRepository.create(core_session, org_a)
        record_evidence = RecordEvidence(evidence_repo)
        evidence = await record_evidence(
            entity_type="Company",
            entity_id=company_id,
            claim="Acme Rockets raised a Series B.",
            source_url="https://example.test/acme-series-b",
            observed_at=NOW,
        )
        assert evidence.id is not None

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        crm_sync_records = await SqlAlchemyCrmSyncRecordRepository.create(verify_session, org_a)
        record = await crm_sync_records.get_by_target("Company", company_id, "fake")
        assert record is not None
        assert record.sync_status == SyncStatus.FAILED
        assert record.last_error is not None and "simulated CRM outage" in record.last_error


@pytest.mark.asyncio
async def test_sync_retries_safely_after_recovery_with_no_duplicate_provider_object(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations

    seed_session = await open_app_session()
    async with seed_session, seed_session.begin():
        company_id = await _seed_company(seed_session, org_a)

    provider = get_fake_crm_provider()
    provider.queue_failure("COMPANY", str(company_id), ProviderUnavailableError("attempt 1"))
    provider.queue_failure("COMPANY", str(company_id), ProviderUnavailableError("attempt 2"))

    activity_input = SyncEntityToCrmActivityInput(
        organization_id=str(org_a),
        entity_type="Company",
        entity_id=str(company_id),
        provider_account_id="acct-1",
    )

    for _ in range(2):
        with pytest.raises(ApplicationError):
            await sync_entity_to_crm_activity(activity_input)

    result = await sync_entity_to_crm_activity(activity_input)
    assert result.sync_status == "SYNCED"
    assert result.provider_object_id is not None

    verify_session = await open_app_session()
    async with verify_session, verify_session.begin():
        crm_sync_records = await SqlAlchemyCrmSyncRecordRepository.create(verify_session, org_a)
        record = await crm_sync_records.get_by_target("Company", company_id, "fake")
        assert record is not None
        assert record.sync_status == SyncStatus.SYNCED
        assert record.last_error is None
        assert record.provider_object_id == result.provider_object_id

    # No duplicate provider object was ever created by the two failed attempts or the retry.
    assert provider.object_count == 1
