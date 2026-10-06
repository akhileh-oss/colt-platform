"""`ProcessBounce` (CLAUDE.md §10.18, §18.1, §18.2, §29, Milestone 17).

A hard bounce means the address does not work: §18.1's "global outbound suppression must be
modeled explicitly" and "no campaign or agent may override a suppression entry" apply to bounces
exactly as they do to unsubscribes, so this use case drives the same `AddSuppressionEntry`
mechanism Milestone 16 built, with `reason=BOUNCE`. It also marks the `Person`'s email
`INVALID` (§11's email-status machine, Milestone 11) and threads a `bounced` event onto the
lead's email conversation.

No real commercial email provider's bounce webhook exists in this environment (same "no real
X" posture as Milestone 12's signal sources), and Mailpit does not generate real bounces — this
use case is proven hermetically only, against a fake bounce notification shaped like a real
provider's would be, not against a live bounce from Milestone 17's own acceptance-criterion
integration test.
"""

from __future__ import annotations

from datetime import datetime

from colt_application.errors import NotFoundError
from colt_application.ports.conversation_event_repository import ConversationEventRepository
from colt_application.ports.conversation_repository import ConversationRepository
from colt_application.ports.lead_repository import LeadRepository
from colt_application.ports.message_repository import MessageRepository
from colt_application.ports.person_repository import PersonRepository
from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_domain import ConversationEvent, EmailStatus, SuppressionReason

_EMAIL_CHANNEL = "email"


class ProcessBounce:
    def __init__(
        self,
        messages: MessageRepository,
        leads: LeadRepository,
        people: PersonRepository,
        conversations: ConversationRepository,
        conversation_events: ConversationEventRepository,
        add_suppression_entry: AddSuppressionEntry,
    ) -> None:
        self._messages = messages
        self._leads = leads
        self._people = people
        self._conversations = conversations
        self._conversation_events = conversation_events
        self._add_suppression_entry = add_suppression_entry

    async def __call__(
        self, *, provider_message_id: str, reason: str, bounced_at: datetime
    ) -> ConversationEvent:
        original = await self._messages.get_by_provider_message_id(provider_message_id)
        if original is None:
            raise NotFoundError(
                f"No outbound message with provider_message_id {provider_message_id!r} — "
                "cannot process this bounce."
            )

        lead = await self._leads.get(original.lead_id)
        if lead is None:
            raise NotFoundError(f"Bounced message {original.id} has no resolvable lead.")

        person = await self._people.get(lead.person_id)
        if person is None or not person.email:
            raise NotFoundError(f"Lead {lead.id} has no resolvable email address to suppress.")

        await self._add_suppression_entry(
            identifier_type="email",
            identifier=person.email,
            reason=SuppressionReason.BOUNCE,
            source="email_bounce",
        )
        await self._people.update(person.id, email_status=EmailStatus.INVALID)

        conversation = await self._conversations.get_by_lead_and_channel(lead.id, _EMAIL_CHANNEL)
        if conversation is None:
            conversation = await self._conversations.add(
                lead_id=lead.id, channel=_EMAIL_CHANNEL, last_activity_at=bounced_at
            )
        await self._conversations.touch_last_activity(conversation.id, at=bounced_at)

        return await self._conversation_events.add(
            conversation_id=conversation.id,
            event_type="bounced",
            occurred_at=bounced_at,
            metadata={"provider_message_id": provider_message_id, "reason": reason},
        )
