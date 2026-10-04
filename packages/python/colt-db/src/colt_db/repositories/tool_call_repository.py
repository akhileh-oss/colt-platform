"""Tenant-scoped repository for `ToolCall` (CLAUDE.md §10.16)."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from colt_db.mappers import tool_call_to_domain
from colt_db.models.tool_call import ToolCallModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import ToolCall, ToolCallStatus


class SqlAlchemyToolCallRepository(TenantScopedRepository):
    async def start(
        self,
        *,
        agent_run_id: UUID,
        tool_name: str,
        tool_version: str,
        arguments_redacted: str,
        provider: str | None = None,
    ) -> ToolCall:
        model = ToolCallModel(
            agent_run_id=agent_run_id,
            organization_id=self.organization_id,
            tool_name=tool_name,
            tool_version=tool_version,
            arguments_redacted=arguments_redacted,
            provider=provider,
            status=ToolCallStatus.RUNNING.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return tool_call_to_domain(model)

    async def succeed(
        self, tool_call_id: UUID, *, at: datetime, result_summary: str, latency_ms: float
    ) -> ToolCall:
        model = await self._get_model(tool_call_id)
        model.status = ToolCallStatus.SUCCEEDED.value
        model.completed_at = at
        model.result_summary = result_summary
        model.latency_ms = latency_ms
        await self._session.flush()
        await self._session.refresh(model)
        return tool_call_to_domain(model)

    async def fail(
        self, tool_call_id: UUID, *, at: datetime, error_code: str, latency_ms: float
    ) -> ToolCall:
        model = await self._get_model(tool_call_id)
        model.status = ToolCallStatus.FAILED.value
        model.completed_at = at
        model.error_code = error_code
        model.latency_ms = latency_ms
        await self._session.flush()
        await self._session.refresh(model)
        return tool_call_to_domain(model)

    async def list_for_run(self, agent_run_id: UUID) -> list[ToolCall]:
        stmt = self._select_scoped(ToolCallModel).where(ToolCallModel.agent_run_id == agent_run_id)
        models = (await self._session.execute(stmt)).scalars().all()
        return [tool_call_to_domain(model) for model in models]

    async def _get_model(self, tool_call_id: UUID) -> ToolCallModel:
        stmt = self._select_scoped(ToolCallModel).where(ToolCallModel.id == tool_call_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            raise ValueError(f"No tool call {tool_call_id} in this organization.")
        return cast(ToolCallModel, model)
