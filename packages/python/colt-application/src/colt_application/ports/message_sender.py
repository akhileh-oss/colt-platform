"""The MessageSender port (CLAUDE.md §17, §29) — the one place `SendMessage` is allowed to
cause an actual external side effect.

No real implementation exists yet: `CLAUDE.md` §29's email subsystem, the first real channel
provider, is Milestone 17's job. `SendMessage`'s whole point in this milestone is the gate in
front of this port, not what is behind it — proven in tests with a fake that records whether it
was ever called, which is exactly what "a policy violation cannot result in an external message
send" (§68 Milestone 16's acceptance criterion) asks to be shown.
"""

from __future__ import annotations

from typing import Protocol

from colt_domain import Message


class MessageSender(Protocol):
    async def send(self, message: Message) -> str:
        """Send `message` through its own channel and return the provider's message id."""
        ...
