"""`EmailMessageSender` (CLAUDE.md §29.1, Milestone 17) — hermetic: a fake `EmailProvider` and a
fake lead/step message lookup, proving the threading resolution (most recent prior send's
`provider_message_id` becomes this send's `In-Reply-To`) and the unsubscribe URL shape, without
any real SMTP or database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from colt_domain import Message, Person
from colt_integrations.email.message_sender import EmailMessageSender
from colt_integrations.email.port import SentEmail

NOW = datetime.now(UTC)


class FakeEmailProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send(
        self,
        *,
        to_email: str,
        to_name: str | None,
        subject: str,
        body_text: str,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        unsubscribe_url: str | None = None,
    ) -> SentEmail:
        self.calls.append(
            {
                "to_email": to_email,
                "to_name": to_name,
                "subject": subject,
                "body_text": body_text,
                "in_reply_to": in_reply_to,
                "references": references,
                "unsubscribe_url": unsubscribe_url,
            }
        )
        return SentEmail(message_id="<new-send@colt.local>")


class FakeMessageLookup:
    def __init__(self, prior: list[Message]) -> None:
        self._prior = prior

    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]:
        return self._prior


def _message(lead_id: UUID, *, sequence_step_id: UUID | None = None) -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=lead_id,
        sequence_step_id=sequence_step_id,
        channel="email",
        subject="Hi",
        body="Hello.",
        created_at=NOW,
        updated_at=NOW,
    )


def _person(email: str = "lead@example.com") -> Person:
    return Person(
        id=uuid4(),
        organization_id=uuid4(),
        company_id=uuid4(),
        full_name="Lead Person",
        email=email,
        created_at=NOW,
        updated_at=NOW,
    )


async def test_sends_with_no_threading_when_there_is_no_prior_message() -> None:
    lead_id = uuid4()
    message = _message(lead_id)
    provider = FakeEmailProvider()
    sender = EmailMessageSender(
        provider,
        FakeMessageLookup([message]),
        unsubscribe_url_base="https://colt.local/unsubscribe",
    )

    provider_message_id = await sender.send(message, recipient=_person())

    assert provider_message_id == "<new-send@colt.local>"
    (call,) = provider.calls
    assert call["in_reply_to"] is None
    assert call["references"] is None
    assert (
        call["unsubscribe_url"]
        == f"https://colt.local/unsubscribe/{message.organization_id}/{message.id}"
    )


async def test_threads_off_the_most_recent_prior_send_in_the_same_sequence_step() -> None:
    lead_id = uuid4()
    step_id = uuid4()
    earlier = _message(lead_id, sequence_step_id=step_id).model_copy(
        update={"provider_message_id": "<earlier@colt.local>", "status": "SENT"}
    )
    newest_prior = _message(lead_id, sequence_step_id=step_id).model_copy(
        update={"provider_message_id": "<newest-prior@colt.local>", "status": "SENT"}
    )
    message = _message(lead_id, sequence_step_id=step_id)
    provider = FakeEmailProvider()
    sender = EmailMessageSender(
        provider,
        FakeMessageLookup([earlier, newest_prior, message]),
        unsubscribe_url_base="https://colt.local/unsubscribe",
    )

    await sender.send(message, recipient=_person())

    (call,) = provider.calls
    assert call["in_reply_to"] == "<newest-prior@colt.local>"
    assert call["references"] == ["<newest-prior@colt.local>"]


async def test_raises_when_the_recipient_has_no_email() -> None:
    lead_id = uuid4()
    message = _message(lead_id)
    provider = FakeEmailProvider()
    sender = EmailMessageSender(
        provider,
        FakeMessageLookup([message]),
        unsubscribe_url_base="https://colt.local/unsubscribe",
    )
    recipient = _person().model_copy(update={"email": None})

    with pytest.raises(ValueError, match="no email address"):
        await sender.send(message, recipient=recipient)

    assert provider.calls == []
