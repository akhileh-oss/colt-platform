"""Deterministic channel-performance summary (CLAUDE.md §68, Milestone 22's "channel
performance" Build item), grouped by the free-text `channel` field both `Message` and
`Conversation` already carry. Answers the acceptance criterion's "what channels ... produce
commercial outcomes" via `Conversation.state` — a channel whose conversations land on
`POSITIVE` more often is the literal commercial-outcome signal this report surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass

from colt_domain import Conversation, ConversationState, Message


@dataclass(frozen=True, slots=True)
class ChannelPerformanceRow:
    channel: str
    message_count: int
    sent_count: int
    conversation_count: int
    positive_count: int
    positive_rate: float


@dataclass(slots=True)
class _MessageBucket:
    message_count: int = 0
    sent_count: int = 0


@dataclass(slots=True)
class _ConversationBucket:
    conversation_count: int = 0
    positive_count: int = 0


def summarize_channel_performance(
    messages: list[Message], conversations: list[Conversation]
) -> list[ChannelPerformanceRow]:
    message_totals: dict[str, _MessageBucket] = {}
    for message in messages:
        message_bucket = message_totals.setdefault(message.channel, _MessageBucket())
        message_bucket.message_count += 1
        if message.status == "SENT":
            message_bucket.sent_count += 1

    conversation_totals: dict[str, _ConversationBucket] = {}
    for conversation in conversations:
        conversation_bucket = conversation_totals.setdefault(
            conversation.channel, _ConversationBucket()
        )
        conversation_bucket.conversation_count += 1
        if conversation.state is ConversationState.POSITIVE:
            conversation_bucket.positive_count += 1

    channels = sorted(set(message_totals) | set(conversation_totals))
    rows = []
    for channel in channels:
        message_bucket = message_totals.get(channel, _MessageBucket())
        conversation_bucket = conversation_totals.get(channel, _ConversationBucket())
        positive_rate = (
            conversation_bucket.positive_count / conversation_bucket.conversation_count
            if conversation_bucket.conversation_count
            else 0.0
        )
        rows.append(
            ChannelPerformanceRow(
                channel=channel,
                message_count=message_bucket.message_count,
                sent_count=message_bucket.sent_count,
                conversation_count=conversation_bucket.conversation_count,
                positive_count=conversation_bucket.positive_count,
                positive_rate=positive_rate,
            )
        )
    return rows
