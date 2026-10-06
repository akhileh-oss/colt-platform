"""`determine_conversation_transition` (CLAUDE.md §11.2, §12.10, §23.1, Milestone 19)."""

from __future__ import annotations

import pytest

from colt_application.reply_classification import Urgency, determine_conversation_transition
from colt_domain import ConversationState


@pytest.mark.parametrize(
    "recommended",
    [
        ConversationState.POSITIVE,
        ConversationState.QUESTION,
        ConversationState.OBJECTION,
        ConversationState.NOT_NOW,
        ConversationState.NOT_INTERESTED,
    ],
)
def test_a_low_or_medium_urgency_reply_applies_the_models_own_recommendation(
    recommended: ConversationState,
) -> None:
    applied = determine_conversation_transition(
        current_state=ConversationState.OPEN, recommended_state=recommended, urgency=Urgency.LOW
    )
    assert applied == recommended


def test_high_urgency_always_produces_a_handoff_even_if_the_model_recommended_otherwise() -> None:
    applied = determine_conversation_transition(
        current_state=ConversationState.OPEN,
        recommended_state=ConversationState.QUESTION,
        urgency=Urgency.HIGH,
    )
    assert applied == ConversationState.HUMAN_HANDOFF


@pytest.mark.parametrize(
    "terminal_state", [ConversationState.UNSUBSCRIBED, ConversationState.HUMAN_HANDOFF]
)
def test_a_terminal_conversation_never_moves_again_from_a_later_reply(
    terminal_state: ConversationState,
) -> None:
    applied = determine_conversation_transition(
        current_state=terminal_state,
        recommended_state=ConversationState.POSITIVE,
        urgency=Urgency.HIGH,
    )
    assert applied == terminal_state
