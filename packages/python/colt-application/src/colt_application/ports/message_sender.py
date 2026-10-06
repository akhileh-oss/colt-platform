"""The MessageSender port (CLAUDE.md §17, §29) — the one place `SendMessage` is allowed to
cause an actual external side effect.

Milestone 16 defined this port with no real implementation: Milestone 17's email subsystem is
the first real channel provider. `recipient` is this milestone's own addition to the signature
— `SendMessage` already resolves the lead's `Person` for its own `target_identity_valid` check,
so passing that same, already-fetched entity through to the sender avoids a second lookup
inside the adapter, rather than narrowing it to a bare `to_email: str` that would need
re-deriving per channel (email needs `person.email`; a hypothetical future channel might need
`person.linkedin_url` instead) every time a new channel adapter is added.
"""

from __future__ import annotations

from typing import Protocol

from colt_domain import Message, Person


class MessageSender(Protocol):
    async def send(self, message: Message, *, recipient: Person) -> str:
        """Send `message` to `recipient` through its own channel and return the provider's
        message id."""
        ...
