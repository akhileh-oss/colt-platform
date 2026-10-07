"""Tenant-scoped repository for `AgentRun` (CLAUDE.md §10.15).

Unlike every repository before it, this one updates a row after creating it — `start()` writes
the `RUNNING` record an `AgentRun` begins as, and `complete()`/`fail()` close it out once the
agent finishes. There is no `update()`: closing a run two different ways is two different,
narrowly-named methods, so a caller can't accidentally leave a run row half-filled.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from colt_db.mappers import agent_run_to_domain
from colt_db.models.agent_run import AgentRunModel
from colt_db.tenancy import TenantScopedRepository
from colt_domain import AgentRun, AgentRunStatus


class SqlAlchemyAgentRunRepository(TenantScopedRepository):
    async def start(
        self,
        *,
        agent_name: str,
        agent_version: str,
        model_name: str,
        input_hash: str,
        workflow_id: str | None = None,
        workflow_run_id: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        prompt_version: str | None = None,
    ) -> AgentRun:
        model = AgentRunModel(
            organization_id=self.organization_id,
            agent_name=agent_name,
            agent_version=agent_version,
            model_name=model_name,
            input_hash=input_hash,
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            entity_type=entity_type,
            entity_id=entity_id,
            prompt_version=prompt_version,
            status=AgentRunStatus.RUNNING.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return agent_run_to_domain(model)

    async def complete(
        self,
        run_id: UUID,
        *,
        at: datetime,
        input_tokens: int,
        output_tokens: int,
        tool_tokens: int,
        estimated_cost_usd: float | None,
        output_json: dict[str, Any] | None,
    ) -> AgentRun:
        model = await self._get_model(run_id)
        model.status = AgentRunStatus.COMPLETED.value
        model.completed_at = at
        model.input_tokens = input_tokens
        model.output_tokens = output_tokens
        model.tool_tokens = tool_tokens
        model.estimated_cost_usd = estimated_cost_usd
        model.output_json = output_json
        await self._session.flush()
        await self._session.refresh(model)
        return agent_run_to_domain(model)

    async def fail(
        self, run_id: UUID, *, at: datetime, error_code: str, error_message: str
    ) -> AgentRun:
        model = await self._get_model(run_id)
        model.status = AgentRunStatus.FAILED.value
        model.completed_at = at
        model.error_code = error_code
        model.error_message = error_message
        await self._session.flush()
        await self._session.refresh(model)
        return agent_run_to_domain(model)

    async def get(self, run_id: UUID) -> AgentRun | None:
        stmt = self._select_scoped(AgentRunModel).where(AgentRunModel.id == run_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return agent_run_to_domain(model) if model is not None else None

    async def list_all(self) -> list[AgentRun]:
        """Every agent run in this organization — the agent-cost/model-performance analytics
        read models (Milestone 22) group over this by `agent_name`/`model_name`. No prior
        milestone's Build list needed a bulk read of this table."""
        stmt = self._select_scoped(AgentRunModel)
        models = (await self._session.execute(stmt)).scalars().all()
        return [agent_run_to_domain(model) for model in models]

    async def _get_model(self, run_id: UUID) -> AgentRunModel:
        stmt = self._select_scoped(AgentRunModel).where(AgentRunModel.id == run_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            raise ValueError(f"No agent run {run_id} in this organization.")
        return cast(AgentRunModel, model)
