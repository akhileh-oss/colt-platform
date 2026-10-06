"""The ``/api/v1`` router (CLAUDE.md §25).

Versioned routes are mounted here. A breaking change means a new version module, never an
in-place change to this one.
"""

from __future__ import annotations

from fastapi import APIRouter

from colt_api.routers.v1 import campaigns, me, meta, observability, unsubscribe

API_V1_PREFIX = "/api/v1"

router = APIRouter(prefix=API_V1_PREFIX)
router.include_router(meta.router)
router.include_router(me.router)
router.include_router(observability.router)
router.include_router(campaigns.router)
router.include_router(unsubscribe.router)
