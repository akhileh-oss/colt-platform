"""Deterministic channel-performance summary (CLAUDE.md §68, Milestone 22)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_application.channel_performance import summarize_channel_performance
from colt_domain import Conversation, ConversationState, Message

NOW = datetime.now(UTC)


def _message(*, channel: str, status: str = "DRAFT") -> Message:
    return Message(
        id=uuid4(),
        organization_id=uuid4(),
        campaign_id=uuid4(),
        lead_id=uuid4(),
        channel=channel,
        body="hello",
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def _conversation(
    *, channel: str, state: ConversationState = ConversationState.OPEN
) -> Conversation:
    return Conversation(
        id=uuid4(),
        organization_id=uuid4(),
        lead_id=uuid4(),
        channel=channel,
        state=state,
        created_at=NOW,
        updated_at=NOW,
    )


def test_message_counts_group_by_channel() -> None:
    messages = [
        _message(channel="email"),
        _message(channel="email", status="SENT"),
        _message(channel="linkedin"),
    ]

    rows = {row.channel: row for row in summarize_channel_performance(messages, [])}

    assert rows["email"].message_count == 2
    assert rows["email"].sent_count == 1
    assert rows["linkedin"].message_count == 1


def test_conversation_counts_group_by_channel() -> None:
    conversations = [
        _conversation(channel="email", state=ConversationState.POSITIVE),
        _conversation(channel="email", state=ConversationState.OPEN),
        _conversation(channel="linkedin", state=ConversationState.POSITIVE),
    ]

    rows = {row.channel: row for row in summarize_channel_performance([], conversations)}

    assert rows["email"].conversation_count == 2
    assert rows["email"].positive_count == 1
    assert rows["linkedin"].positive_rate == 1.0


def test_a_channel_with_messages_but_no_conversations_has_zero_positive_rate() -> None:
    messages = [_message(channel="email")]

    rows = summarize_channel_performance(messages, [])

    assert rows[0].channel == "email"
    assert rows[0].conversation_count == 0
    assert rows[0].positive_rate == 0.0


def test_a_channel_with_conversations_but_no_messages_still_appears() -> None:
    conversations = [_conversation(channel="linkedin")]

    rows = summarize_channel_performance([], conversations)

    assert rows[0].channel == "linkedin"
    assert rows[0].message_count == 0


def test_rows_are_sorted_by_channel_name() -> None:
    messages = [_message(channel="sms"), _message(channel="email")]

    rows = summarize_channel_performance(messages, [])

    assert [row.channel for row in rows] == ["email", "sms"]
