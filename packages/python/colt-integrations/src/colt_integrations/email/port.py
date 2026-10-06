"""The email provider port (CLAUDE.md §2.7, §29 — "Email deserves its own subsystem").

`SentEmail.message_id` is the RFC822 `Message-ID` header the adapter itself generates and sets
on the outgoing message — SMTP has no server-assigned send ID the way a REST API returns one
(Apollo, Brave), so the standards-based identifier is the one CLAUDE.md §29.1 asks to be
persisted: "Persist provider message IDs and conversation/thread IDs where available." It is
also what an inbound reply's `In-Reply-To` header will reference, so it is this subsystem's one
threading key end to end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SentEmail:
    message_id: str


class EmailProvider(Protocol):
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
    ) -> SentEmail: ...
