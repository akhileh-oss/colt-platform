"""`sync_entity_to_crm_activity` (CLAUDE.md §30, Milestone 20) — the one place a CRM provider is
actually called. Opens its own tenant-scoped session (this activity runs outside the workflow
sandbox, the same reason `send_email_activity` does), loads whichever Colt entity is being synced
straight from Postgres (for `Task`, which Colt has no native entity for, the caller's own
`fields` are used instead), calls the configured `CRMProvider` (only `FakeCRMProvider` exists —
no real CRM vendor is named by CLAUDE.md §30, the same posture Milestone 12's
`SignalTriggerSource` already documents), and records the outcome via `RecordCrmSyncOutcome` —
success or failure, idempotently upserted by `(entity_type, entity_id, provider_name)`.

A `ProviderError` is retried according to its own `.retryable` classification (§28.1), the same
rule `send_email_activity` applies to the SMTP adapter: a transient `rate_limit`/`timeout`/`500`
is worth a retry (Temporal's own `RetryPolicy`, configured on the workflow side), an
`invalid_payload`/auth rejection is not. Either way `RecordCrmSyncOutcome` writes the attempt's
outcome before this activity returns or re-raises, so "CRM outage does not break core Colt
workflows" (§30's acceptance criterion) never depends on this activity's own retry succeeding —
the `CrmSyncRecord` row is the durable account of what happened, independent of whether Temporal
keeps retrying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from colt_application.errors import NotFoundError
from colt_application.use_cases.record_crm_sync_outcome import RecordCrmSyncOutcome
from colt_config import get_settings
from colt_db import get_default_engine, make_session_factory
from colt_db.repositories import (
    SqlAlchemyCompanyRepository,
    SqlAlchemyCrmSyncRecordRepository,
    SqlAlchemyOpportunityRepository,
    SqlAlchemyPersonRepository,
)
from colt_integrations.crm.fake import FakeCRMProvider
from colt_integrations.crm.port import CRMProvider, CrmSyncResult
from colt_integrations.errors import ProviderError
from colt_observability import get_logger

logger = get_logger(__name__)

#: The only provider this milestone builds (CLAUDE.md §30 names no real CRM vendor). Kept as a
#: module-level singleton so a reconciliation run's retries against the same fake target the same
#: in-memory objects — a real adapter would need no such thing, since a real CRM is itself the
#: shared state across calls.
_FAKE_CRM_PROVIDER = FakeCRMProvider()


def get_fake_crm_provider() -> FakeCRMProvider:
    """Test seam: inject queued failures into the activity's own provider instance."""
    return _FAKE_CRM_PROVIDER


@dataclass(frozen=True)
class SyncEntityToCrmActivityInput:
    """Explicit input schema (CLAUDE.md §24.2). UUIDs travel as `str`, matching every other
    activity's input in this package."""

    organization_id: str
    entity_type: str  # "Company" | "Person" | "Opportunity" | "Task"
    entity_id: str
    provider_account_id: str
    fields: dict[str, Any] = field(default_factory=dict)  # only read for "Task"


@dataclass(frozen=True)
class SyncEntityToCrmActivityOutput:
    sync_status: str
    provider_object_id: str | None
    last_error: str | None


def _resolve_provider(settings_provider: str) -> CRMProvider:
    if settings_provider != "fake":
        raise ApplicationError(
            f"No real CRM adapter is configured in this environment (CRM_PROVIDER="
            f"{settings_provider!r}). Only 'fake' is supported.",
            non_retryable=True,
        )
    return _FAKE_CRM_PROVIDER


async def _load_fields(
    entity_type: str,
    entity_id: UUID,
    *,
    companies: SqlAlchemyCompanyRepository,
    persons: SqlAlchemyPersonRepository,
    opportunities: SqlAlchemyOpportunityRepository,
    given_fields: dict[str, Any],
) -> dict[str, Any]:
    if entity_type == "Company":
        company = await companies.get(entity_id)
        if company is None:
            raise NotFoundError(f"No company found with id {entity_id}.")
        return {
            "name": company.name,
            "domain": company.domain,
            "industry": company.industry,
            "website_url": company.website_url,
        }
    if entity_type == "Person":
        person = await persons.get(entity_id)
        if person is None:
            raise NotFoundError(f"No person found with id {entity_id}.")
        return {
            "full_name": person.full_name,
            "email": person.email,
            "title": person.title,
            "company_id": str(person.company_id),
        }
    if entity_type == "Opportunity":
        opportunity = await opportunities.get(entity_id)
        if opportunity is None:
            raise NotFoundError(f"No opportunity found with id {entity_id}.")
        return {
            "pipeline_stage": opportunity.pipeline_stage.value,
            "estimated_value": opportunity.estimated_value,
            "currency": opportunity.currency,
        }
    if entity_type == "Task":
        return given_fields
    raise ApplicationError(f"Unknown CRM-syncable entity_type {entity_type!r}.", non_retryable=True)


async def _sync(
    provider: CRMProvider, entity_type: str, *, external_id: str, fields: dict[str, Any]
) -> CrmSyncResult:
    if entity_type == "Company":
        return await provider.sync_company(external_id=external_id, fields=fields)
    if entity_type == "Person":
        return await provider.sync_contact(external_id=external_id, fields=fields)
    if entity_type == "Opportunity":
        return await provider.sync_opportunity(external_id=external_id, fields=fields)
    return await provider.sync_task(external_id=external_id, fields=fields)


@activity.defn
async def sync_entity_to_crm_activity(
    input: SyncEntityToCrmActivityInput,
) -> SyncEntityToCrmActivityOutput:
    settings = get_settings()
    organization_id = UUID(input.organization_id)
    entity_id = UUID(input.entity_id)
    now = datetime.now(UTC)

    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        companies = await SqlAlchemyCompanyRepository.create(session, organization_id)
        persons = SqlAlchemyPersonRepository(session, organization_id)
        opportunities = SqlAlchemyOpportunityRepository(session, organization_id)
        crm_sync_records = SqlAlchemyCrmSyncRecordRepository(session, organization_id)
        record_outcome = RecordCrmSyncOutcome(crm_sync_records)

        try:
            fields = await _load_fields(
                input.entity_type,
                entity_id,
                companies=companies,
                persons=persons,
                opportunities=opportunities,
                given_fields=input.fields,
            )
        except NotFoundError as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc

        provider = _resolve_provider(settings.crm.provider)

        try:
            result = await _sync(
                provider, input.entity_type, external_id=str(entity_id), fields=fields
            )
        except ProviderError as exc:
            record = await record_outcome(
                entity_type=input.entity_type,
                entity_id=entity_id,
                provider_name=settings.crm.provider,
                provider_account_id=input.provider_account_id,
                provider_object_id=None,
                error=str(exc),
                now=now,
            )
            await session.commit()
            logger.info(
                "crm sync activity failed",
                extra={"operation": "sync_entity_to_crm_activity", "retryable": exc.retryable},
            )
            raise ApplicationError(str(exc), non_retryable=not exc.retryable) from exc

        record = await record_outcome(
            entity_type=input.entity_type,
            entity_id=entity_id,
            provider_name=settings.crm.provider,
            provider_account_id=input.provider_account_id,
            provider_object_id=result.provider_object_id,
            error=None,
            now=now,
        )
        await session.commit()

    logger.info(
        "crm sync activity completed",
        extra={"operation": "sync_entity_to_crm_activity", "sync_status": record.sync_status.value},
    )
    return SyncEntityToCrmActivityOutput(
        sync_status=record.sync_status.value,
        provider_object_id=record.provider_object_id,
        last_error=record.last_error,
    )
