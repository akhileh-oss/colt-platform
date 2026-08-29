"""Service metadata (CLAUDE.md §25).

The first ``/api/v1`` resource: it gives clients a cheap way to confirm which build and
environment they are talking to, and gives the generated client something to exercise.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from colt_api import __version__
from colt_api.dependencies import SettingsDep

router = APIRouter(prefix="/meta", tags=["meta"])


class MetaResponse(BaseModel):
    name: str = Field(description="Application name.")
    version: str = Field(description="Running API version.")
    environment: str = Field(description="Deployment environment.")
    api_version: str = Field(description="API contract version.")


@router.get("", response_model=MetaResponse, summary="Service metadata")
async def get_meta(settings: SettingsDep) -> MetaResponse:
    """Return non-sensitive information about the running service."""
    return MetaResponse(
        name=settings.app.name,
        version=__version__,
        environment=settings.app.env.value,
        api_version="v1",
    )
