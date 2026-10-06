"""Deterministic conversation-state transition logic (CLAUDE.md §11.2, §12.10, §23.1,
Milestone 19) — "application services = deterministic business logic," the same reasoning
`colt_application.research`/`colt_application.scoring` already apply to a model's own judgment.

`ReplyIntelligenceAgent` recommends a transition; this function decides the one actually
applied. Two rules the model's own recommendation can never override: a terminal conversation
(`UNSUBSCRIBED`/`HUMAN_HANDOFF`) never moves again from a later reply, and high urgency always
produces a handoff regardless of what the model recommended — this is what makes Milestone 19's
acceptance criterion ("high-intent replies produce the correct handoff") hold even if the model
forgets to recommend `HUMAN_HANDOFF` itself.
"""

from __future__ import annotations

from enum import StrEnum

from colt_domain import ConversationState


#: §12.10's own field name is `urgency`; the closed set of values a model may report it as.
#: CLAUDE.md gives no explicit vocabulary, so (like `CampaignStatus`, Milestone 14) this is this
#: milestone's own documented, minimal design decision: three levels are enough to decide one
#: binary thing (does this reply need a human right now) without inventing a finer scale no
#: downstream code reads.
class Urgency(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


#: A terminal conversation (already unsubscribed or already handed off to a human) never moves
#: again on a later reply — the opposite would silently undo a human's or an unsubscribe's own
#: decision.
_TERMINAL_STATES = frozenset({ConversationState.UNSUBSCRIBED, ConversationState.HUMAN_HANDOFF})


def determine_conversation_transition(
    *,
    current_state: ConversationState,
    recommended_state: ConversationState,
    urgency: Urgency,
) -> ConversationState:
    """The conversation state Milestone 19's acceptance criterion requires to update
    deterministically — never simply the model's own `recommended_state_transition` field."""
    if current_state in _TERMINAL_STATES:
        return current_state
    if urgency is Urgency.HIGH:
        return ConversationState.HUMAN_HANDOFF
    return recommended_state
