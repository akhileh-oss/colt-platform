"""Dependency-injection conventions for the API (CLAUDE.md §5.1).

Conventions:

* Every injected value is exposed as a module-level ``Annotated`` alias ending in ``Dep``,
  so route signatures stay short and the dependency graph is greppable.
* Routes depend on these aliases, never on concrete infrastructure.
* Nothing here contains business logic; that belongs in the application layer.

Milestone 04 adds the authenticated principal and organization context, Milestone 05 the
database session. Both arrive as further aliases in this module.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from colt_config import Settings, get_settings


def settings_provider() -> Settings:
    """Provide process configuration. Overridable in tests via ``dependency_overrides``."""
    return get_settings()


def request_id_provider(request: Request) -> str:
    """The current request's correlation ID, assigned by RequestContextMiddleware."""
    request_id: str = getattr(request.state, "request_id", "")
    return request_id


SettingsDep = Annotated[Settings, Depends(settings_provider)]
RequestIdDep = Annotated[str, Depends(request_id_provider)]
