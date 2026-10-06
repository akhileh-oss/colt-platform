"""Authorization and business-safety policy engine."""

from colt_policy.outbound import (
    OutboundSendContext,
    PolicyDecision,
    PolicyEvaluation,
    evaluate_outbound_send,
)

__version__ = "0.1.0"

__all__ = [
    "OutboundSendContext",
    "PolicyDecision",
    "PolicyEvaluation",
    "__version__",
    "evaluate_outbound_send",
]
