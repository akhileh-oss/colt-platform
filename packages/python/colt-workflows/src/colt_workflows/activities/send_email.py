"""`send_email_activity` (CLAUDE.md §24, §29, Milestone 17) — the send-queue/workflow Build item.

Opens its own tenant-scoped session (this activity runs outside the workflow sandbox, so it is
the one place in this path allowed to touch Postgres/SMTP directly — §5's layering, the same
reason `count_organizations` opens its own engine rather than being handed a session by its
workflow), wires the real `SqlAlchemy*Repository` adapters and `SmtpEmailProvider` behind
`SendMessage`, and runs the exact same policy-gated send path Milestone 16 built. Nothing about
the send logic is duplicated here: this activity is composition, not reimplementation.

`NotFoundError` and `PolicyDeniedError` are never retryable — retrying either repeats the exact
same denial. A `ProviderError` from the SMTP adapter is retried according to its own
`.retryable` classification (§28.1): a transient `ProviderUnavailableError` (Mailpit/relay
unreachable) is worth a retry, a `ProviderRejectedError` (the server refused the recipient) is
not.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from colt_application.errors import NotFoundError, PolicyDeniedError
from colt_application.use_cases.send_message import SendMessage
from colt_config import get_settings
from colt_db import get_default_engine, make_session_factory
from colt_db.repositories import (
    SqlAlchemyApprovalRepository,
    SqlAlchemyAuditLogRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyPersonRepository,
    SqlAlchemySuppressionRepository,
)
from colt_integrations.email.message_sender import EmailMessageSender
from colt_integrations.email.smtp import SmtpEmailProvider
from colt_integrations.errors import ProviderError
from colt_observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SendEmailActivityInput:
    """Explicit input schema (CLAUDE.md §24.2). UUIDs travel as `str` — the plain JSON data
    converter every other activity in this package already relies on (`ExampleActivityInput`)
    has no built-in `uuid.UUID` support, and there is no reason to add a custom converter for
    two fields this activity itself parses on the first line of its body."""

    organization_id: str
    message_id: str
    auto_approval_enabled: bool = False


@dataclass(frozen=True)
class SendEmailActivityOutput:
    status: str
    provider_message_id: str | None


@activity.defn
async def send_email_activity(input: SendEmailActivityInput) -> SendEmailActivityOutput:
    settings = get_settings()
    organization_id = UUID(input.organization_id)
    message_id = UUID(input.message_id)

    factory = make_session_factory(get_default_engine())
    async with factory() as session:
        messages = await SqlAlchemyMessageRepository.create(session, organization_id)
        campaigns = await SqlAlchemyCampaignRepository.create(session, organization_id)
        leads = await SqlAlchemyLeadRepository.create(session, organization_id)
        persons = await SqlAlchemyPersonRepository.create(session, organization_id)
        evidence = await SqlAlchemyEvidenceRepository.create(session, organization_id)
        suppressions = await SqlAlchemySuppressionRepository.create(session, organization_id)
        approvals = await SqlAlchemyApprovalRepository.create(session, organization_id)
        audit_logs = await SqlAlchemyAuditLogRepository.create(session, organization_id)

        provider = SmtpEmailProvider(settings.email)
        sender = EmailMessageSender(
            provider, messages, unsubscribe_url_base=f"{settings.app.base_url}/unsubscribe"
        )
        send_message = SendMessage(
            messages,
            campaigns,
            leads,
            persons,
            evidence,
            suppressions,
            approvals,
            sender,
            audit_logs,
        )

        try:
            result = await send_message(
                message_id, now=datetime.now(UTC), auto_approval_enabled=input.auto_approval_enabled
            )
        except (NotFoundError, PolicyDeniedError) as exc:
            raise ApplicationError(str(exc), non_retryable=True) from exc
        except ProviderError as exc:
            raise ApplicationError(str(exc), non_retryable=not exc.retryable) from exc

        await session.commit()

    logger.info(
        "email send activity completed",
        extra={"operation": "send_email_activity", "status": result.status},
    )
    return SendEmailActivityOutput(
        status=result.status, provider_message_id=result.provider_message_id
    )
