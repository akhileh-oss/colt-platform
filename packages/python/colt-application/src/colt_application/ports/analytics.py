"""Read-only "list everything in this organization" ports for analytics (CLAUDE.md §68,
Milestone 22).

Deliberately separate `Protocol`s from `LeadRepository`/`CompanyRepository`/etc. rather than
adding a `list_all()` method to each of those — a `Protocol` only requires structural
conformance for the type it is actually used as (§2.7's own reasoning), so a second, narrower
Protocol over the same concrete `SqlAlchemy*Repository` classes costs nothing and, critically,
does not retroactively require every existing test double for those wider ports (`FakeLead
Repository`, `FakeCompanyRepository`, etc., used across a dozen other use cases' tests) to grow
a method they never needed. The concrete repositories already gained a real `list_all()` this
milestone; these Protocols are just a second, smaller lens onto the same classes.
"""

from __future__ import annotations

from typing import Protocol

from colt_domain import AgentRun, Company, Conversation, Lead, Message, Person, Signal


class LeadAnalyticsReader(Protocol):
    async def list_all(self) -> list[Lead]: ...


class CompanyAnalyticsReader(Protocol):
    async def list_all(self) -> list[Company]: ...


class PersonAnalyticsReader(Protocol):
    async def list_all(self) -> list[Person]: ...


class SignalAnalyticsReader(Protocol):
    async def list_all(self) -> list[Signal]: ...


class MessageAnalyticsReader(Protocol):
    async def list_all(self) -> list[Message]: ...


class ConversationAnalyticsReader(Protocol):
    async def list_all(self) -> list[Conversation]: ...


class AgentRunAnalyticsReader(Protocol):
    async def list_all(self) -> list[AgentRun]: ...
