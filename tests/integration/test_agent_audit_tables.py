"""Milestone 09 — agent-run and tool-call persistence (CLAUDE.md §10.15, §10.16, §68).

Same proof `test_domain_tables.py` already runs for the Milestone 05 tables, extended to the two
new ones: RLS is enabled/forced/policied, repositories deny cross-tenant access, and the
start/complete lifecycle round-trips correctly through the mapper.

Requires a real Postgres — `make dev`, then `make migrate`. Marked `integration`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from colt_db.repositories.agent_run_repository import SqlAlchemyAgentRunRepository
from colt_db.repositories.tool_call_repository import SqlAlchemyToolCallRepository
from colt_domain import AgentRunStatus, ToolCallStatus

SessionFactory = Callable[[], Awaitable[AsyncSession]]

_TABLES = ("agent_runs", "tool_calls")


@pytest.mark.asyncio
async def test_agent_run_and_tool_call_tables_have_rls_enabled_and_forced(
    open_app_session: SessionFactory,
) -> None:
    session = await open_app_session()
    async with session, session.begin():
        result = await session.execute(
            text(
                "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = ANY(:tables)"
            ),
            {"tables": list(_TABLES)},
        )
        rows = {row.relname: (row.relrowsecurity, row.relforcerowsecurity) for row in result}

    assert set(rows) == set(_TABLES)
    for table, (enabled, forced) in rows.items():
        assert enabled, f"{table} must have Row-Level Security enabled"
        assert forced, f"{table} must FORCE Row-Level Security"


@pytest.mark.asyncio
async def test_agent_run_and_tool_call_tables_have_a_tenant_isolation_policy(
    open_app_session: SessionFactory,
) -> None:
    session = await open_app_session()
    async with session, session.begin():
        result = await session.execute(
            text("SELECT tablename FROM pg_policies WHERE policyname = 'tenant_isolation'")
        )
        tables_with_policy = {row.tablename for row in result}

    assert set(_TABLES) <= tables_with_policy


@pytest.mark.asyncio
async def test_agent_run_lifecycle_round_trips_through_start_and_complete(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyAgentRunRepository.create(session, org_a)
        run = await repo.start(
            agent_name="example-agent",
            agent_version="v1",
            model_name="claude-haiku-4-5-20251001",
            input_hash="deadbeef",
        )
        assert run.status == AgentRunStatus.RUNNING
        assert run.completed_at is None

        completed = await repo.complete(
            run.id,
            at=datetime.now(UTC),
            input_tokens=100,
            output_tokens=20,
            tool_tokens=15,
            estimated_cost_usd=0.0005,
            output_json={"answer": "ok"},
        )

    assert completed.status == AgentRunStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.input_tokens == 100
    assert completed.output_json == {"answer": "ok"}


@pytest.mark.asyncio
async def test_agent_run_lifecycle_round_trips_through_start_and_fail(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations
    session = await open_app_session()
    async with session, session.begin():
        repo = await SqlAlchemyAgentRunRepository.create(session, org_a)
        run = await repo.start(
            agent_name="example-agent",
            agent_version="v1",
            model_name="claude-haiku-4-5-20251001",
            input_hash="deadbeef",
        )
        failed = await repo.fail(
            run.id, at=datetime.now(UTC), error_code="TOOL_FAILED", error_message="boom"
        )

    assert failed.status == AgentRunStatus.FAILED
    assert failed.error_code == "TOOL_FAILED"
    assert failed.error_message == "boom"


@pytest.mark.asyncio
async def test_tool_call_lifecycle_round_trips_and_lists_for_its_run(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, _ = two_organizations
    session = await open_app_session()
    async with session, session.begin():
        run_repo = await SqlAlchemyAgentRunRepository.create(session, org_a)
        run = await run_repo.start(
            agent_name="example-agent",
            agent_version="v1",
            model_name="claude-haiku-4-5-20251001",
            input_hash="deadbeef",
        )
        tool_repo = SqlAlchemyToolCallRepository(session, org_a)
        call = await tool_repo.start(
            agent_run_id=run.id,
            tool_name="get_lead",
            tool_version="v1",
            arguments_redacted='{"lead_id": "[REDACTED]"}',
        )
        assert call.status == ToolCallStatus.RUNNING

        succeeded = await tool_repo.succeed(
            call.id, at=datetime.now(UTC), result_summary="found 1 lead", latency_ms=12.5
        )
        calls = await tool_repo.list_for_run(run.id)

    assert succeeded.status == ToolCallStatus.SUCCEEDED
    assert succeeded.latency_ms == 12.5
    assert len(calls) == 1
    assert calls[0].id == call.id


@pytest.mark.asyncio
async def test_agent_run_repository_denies_cross_tenant_read(
    open_app_session: SessionFactory, two_organizations: tuple[UUID, UUID]
) -> None:
    org_a, org_b = two_organizations

    seed = await open_app_session()
    async with seed, seed.begin():
        repo_b = await SqlAlchemyAgentRunRepository.create(seed, org_b)
        run = await repo_b.start(
            agent_name="example-agent",
            agent_version="v1",
            model_name="claude-haiku-4-5-20251001",
            input_hash="deadbeef",
        )

    session = await open_app_session()
    async with session, session.begin():
        repo_a = await SqlAlchemyAgentRunRepository.create(session, org_a)
        found = await repo_a.get(run.id)

    assert found is None, "org A's repository must not be able to fetch org B's agent run"
