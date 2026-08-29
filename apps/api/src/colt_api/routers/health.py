"""Liveness and readiness endpoints (CLAUDE.md §57).

Deliberately outside ``/api/v1``: probes are infrastructure, not a versioned product contract,
and must keep working across API versions.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from colt_api.readiness import readiness_registry

router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: str = Field(examples=["alive"])


class ReadinessCheckModel(BaseModel):
    ready: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: str = Field(examples=["ready", "not_ready"])
    checks: dict[str, ReadinessCheckModel] = Field(
        description="One entry per required dependency. Empty until Milestone 05 registers one."
    )


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
async def live() -> LivenessResponse:
    """Report that the process is alive.

    Deliberately checks nothing external: making liveness depend on external services invites
    restart storms during a dependency blip (CLAUDE.md §57).
    """
    return LivenessResponse(status="alive")


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def ready(response: Response) -> ReadinessResponse:
    """Report whether the process can accept work.

    Returns 503 when any registered dependency is unhealthy, so a load balancer drains this
    instance instead of sending it traffic it cannot serve.
    """
    results = await readiness_registry.run()
    checks = {r.name: ReadinessCheckModel(ready=r.ready, detail=r.detail) for r in results}
    all_ready = all(r.ready for r in results)

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(status="ready" if all_ready else "not_ready", checks=checks)
