"""`FakeSignalTriggerSource` — the mock trigger Milestone 12's acceptance criterion names
literally ("a real/mock trigger can create a signal and rank it correctly"), and the test
double CLAUDE.md §28.1 requires every adapter to have. Returns exactly the fixture payloads it
was given, once each - calling `poll()` again returns nothing further, the same "drained queue"
behavior a real webhook/feed poll would have once pending events are consumed.
"""

from __future__ import annotations

from colt_integrations.signals.port import SignalTriggerPayload


class FakeSignalTriggerSource:
    def __init__(self, payloads: list[SignalTriggerPayload] | None = None) -> None:
        self._pending = list(payloads or [])

    async def poll(self) -> list[SignalTriggerPayload]:
        pending, self._pending = self._pending, []
        return pending
