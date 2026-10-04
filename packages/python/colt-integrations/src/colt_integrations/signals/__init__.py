"""Signal trigger source port and adapters (CLAUDE.md §12.6)."""

from colt_integrations.signals.fake import FakeSignalTriggerSource
from colt_integrations.signals.port import SignalTriggerPayload, SignalTriggerSource

__all__ = ["FakeSignalTriggerSource", "SignalTriggerPayload", "SignalTriggerSource"]
