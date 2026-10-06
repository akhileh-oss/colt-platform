"""`EmailMessageSender` — the real implementation of `colt_application.ports.message_sender.
MessageSender` for the email channel (CLAUDE.md §29, Milestone 17).

Structurally satisfies that Protocol (an `async def send(self, message, *, recipient) -> str`
method) without importing it: `colt_integrations` depends only on `colt_domain`/`colt_config`/
`colt_observability` (§5's layering), never `colt_application` — the same reasoning every
`colt_db` repository already satisfies its own port by shape, not by inheritance.

`messages` is a `MessageRepository`-shaped dependency (also duck-typed, not imported), used only
to resolve threading (§29.1): before sending, this looks up every other message already sent to
this lead for this sequence step and threads off the most recent one with a `provider_message_
id` — "Incoming messages must resolve to the correct Colt conversation" needs an outgoing
`In-Reply-To` to exist in the first place. Left deliberately simple: threads off the single most
recent prior send, not a full reference chain.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from colt_domain import Message, Person
from colt_integrations.email.port import EmailProvider


class _MessageLookup(Protocol):
    async def list_by_lead_and_step(
        self, lead_id: UUID, sequence_step_id: UUID | None
    ) -> list[Message]: ...


class EmailMessageSender:
    def __init__(
        self, provider: EmailProvider, messages: _MessageLookup, *, unsubscribe_url_base: str
    ) -> None:
        self._provider = provider
        self._messages = messages
        self._unsubscribe_url_base = unsubscribe_url_base

    async def send(self, message: Message, *, recipient: Person) -> str:
        if not recipient.email:
            raise ValueError(f"Person {recipient.id} has no email address to send to.")

        prior = await self._messages.list_by_lead_and_step(
            message.lead_id, message.sequence_step_id
        )
        in_reply_to = next(
            (
                earlier.provider_message_id
                for earlier in reversed(prior)
                if earlier.id != message.id and earlier.provider_message_id
            ),
            None,
        )

        sent = await self._provider.send(
            to_email=recipient.email,
            to_name=recipient.full_name,
            subject=message.subject or "",
            body_text=message.body,
            in_reply_to=in_reply_to,
            references=[in_reply_to] if in_reply_to else None,
            # The unauthenticated unsubscribe endpoint resolves a `MessageRepository` bound to
            # one organization (§27's tenant scoping — RLS denies everything until a session's
            # `app.current_organization_id` is set), and a message id alone carries no
            # organization to bind. `message.organization_id` is not a secret; `message.id` is
            # the unguessable part of this URL that makes the link unforgeable.
            unsubscribe_url=f"{self._unsubscribe_url_base}/{message.organization_id}/{message.id}",
        )
        return sent.message_id
