"""The email unsubscribe endpoint (CLAUDE.md §18.2, §29, Milestone 17).

Deliberately unauthenticated: this is the target of the `List-Unsubscribe`/
`List-Unsubscribe-Post` headers `colt_integrations.email.smtp.SmtpEmailProvider` sets (RFC
8058), which a mail client — not a signed-in Colt user — calls. `organization_id` in the path is
routing information, not a credential (see `UnsubscribeByToken`'s own docstring): it lets this
handler bind the tenant-scoped repositories RLS requires before it can even look up
`message_id`, which is the part of this URL an outside caller cannot guess or forge.

Responds `204` whether or not the token resolves, matching every real unsubscribe-link
convention: confirming or denying a specific `(organization_id, message_id)` pair to an
unauthenticated caller would let that caller enumerate valid ones, and a mail client retrying a
one-click POST must not start seeing errors once the first attempt has already succeeded.

Rate-limited (CLAUDE.md §40, §79, Milestone 24) — the one unauthenticated route in this API, so
the one place an HTTP-layer rate limiter earns its keep today. Keyed by the
`(organization_id, message_id)` pair already in the URL rather than by client IP: a brute-force
attempt against one link looks the same regardless of the caller's network path, and keying by
the token itself needs no IP-extraction logic (`colt_api.rate_limit` explains the full reasoning
behind this milestone's rate-limiting scope).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from colt_api.dependencies import DbSessionDep
from colt_api.rate_limit import rate_limit
from colt_application import AddSuppressionEntry, NotFoundError, UnsubscribeByToken
from colt_db.repositories import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyConversationRepository,
    SqlAlchemyLeadRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyPersonRepository,
    SqlAlchemySuppressionRepository,
)

router = APIRouter(prefix="/unsubscribe", tags=["unsubscribe"])


def _unsubscribe_target(request: Request) -> str:
    return f"{request.path_params['organization_id']}:{request.path_params['message_id']}"


@router.post(
    "/{organization_id}/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unsubscribe the recipient of one sent email",
    dependencies=[Depends(rate_limit("unsubscribe", _unsubscribe_target, limit=10))],
)
async def unsubscribe(organization_id: UUID, message_id: UUID, session: DbSessionDep) -> Response:
    messages = await SqlAlchemyMessageRepository.create(session, organization_id)
    leads = SqlAlchemyLeadRepository(session, organization_id)
    people = SqlAlchemyPersonRepository(session, organization_id)
    conversations = SqlAlchemyConversationRepository(session, organization_id)
    suppressions = SqlAlchemySuppressionRepository(session, organization_id)
    audit_logs = SqlAlchemyAuditLogRepository(session, organization_id)
    add_suppression_entry = AddSuppressionEntry(suppressions, audit_logs)

    unsubscribe_by_token = UnsubscribeByToken(
        messages, leads, people, conversations, add_suppression_entry
    )
    try:
        await unsubscribe_by_token(message_id=message_id, unsubscribed_at=datetime.now(UTC))
    except NotFoundError:
        pass
    else:
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
