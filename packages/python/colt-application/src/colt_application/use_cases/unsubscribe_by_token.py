"""`UnsubscribeByToken` (CLAUDE.md §10.18, §18.1, §18.2, §29, Milestone 17).

"A recognized unsubscribe must: honor it immediately; create/update suppression state; ...
generate an audit event" (§18.2). The "token" is the `Message.id` of the specific email the
`List-Unsubscribe` link was embedded in (set by `colt_integrations.email.smtp.SmtpEmailProvider`)
— a UUIDv4 already has no public mapping back to a person and is never reused, so a signed or
HMAC'd token would add complexity without adding real unforgeability. The link also carries the
message's `organization_id` (see `EmailMessageSender.send`) so the unauthenticated REST endpoint
calling this use case can bind the tenant-scoped repositories it is constructed with before this
use case ever runs — that id is not part of the "token" in the security sense, it is routing
information this use case itself never looks at.

Unsubscribing suppresses the person's email address outbound-wide (via `AddSuppressionEntry`,
the same mechanism Milestone 16 built), terminates that lead's open email conversation if one
exists, and moves the `Lead` to the terminal `UNSUBSCRIBED` status — mirroring how
`DecideMessageApproval` (Milestone 16) advances `Lead` status as a side effect of a messaging
decision, rather than leaving the lead to go stale in a status that no longer reflects reality.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.conversation_repository import ConversationRepository
from colt_application.ports.lead_repository import LeadRepository
from colt_application.ports.message_repository import MessageRepository
from colt_application.ports.person_repository import PersonRepository
from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_domain import ConversationState, Lead, LeadStatus, SuppressionReason

_EMAIL_CHANNEL = "email"


class UnsubscribeByToken:
    def __init__(
        self,
        messages: MessageRepository,
        leads: LeadRepository,
        people: PersonRepository,
        conversations: ConversationRepository,
        add_suppression_entry: AddSuppressionEntry,
    ) -> None:
        self._messages = messages
        self._leads = leads
        self._people = people
        self._conversations = conversations
        self._add_suppression_entry = add_suppression_entry

    async def __call__(self, *, message_id: UUID, unsubscribed_at: datetime) -> Lead:
        message = await self._messages.get(message_id)
        if message is None:
            raise NotFoundError(f"No message {message_id} to resolve this unsubscribe token.")

        lead = await self._leads.get(message.lead_id)
        if lead is None:
            raise NotFoundError(f"Message {message.id} has no resolvable lead.")

        person = await self._people.get(lead.person_id)
        if person is None or not person.email:
            raise NotFoundError(f"Lead {lead.id} has no resolvable email address to suppress.")

        await self._add_suppression_entry(
            identifier_type="email",
            identifier=person.email,
            reason=SuppressionReason.UNSUBSCRIBE,
            source="email_unsubscribe",
        )

        conversation = await self._conversations.get_by_lead_and_channel(lead.id, _EMAIL_CHANNEL)
        if conversation is not None and conversation.state == ConversationState.OPEN:
            await self._conversations.update_state(
                conversation.id, ConversationState.UNSUBSCRIBED, at=unsubscribed_at
            )

        return await self._leads.update_status(lead.id, LeadStatus.UNSUBSCRIBED, at=unsubscribed_at)
