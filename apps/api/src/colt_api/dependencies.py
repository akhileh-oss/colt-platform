"""Dependency-injection conventions for the API (CLAUDE.md §5.1, §26, §27).

Conventions:

* Every injected value is exposed as a module-level ``Annotated`` alias ending in ``Dep``,
  so route signatures stay short and the dependency graph is greppable.
* Routes depend on these aliases, never on concrete infrastructure.
* Nothing here contains business logic; that belongs in the application layer.

Auth chain: ``BearerTokenDep`` extracts the raw token → ``PrincipalDep`` verifies it and
resolves organization context → ``require_permission(...)`` gates a specific capability. A
route that only needs "some authenticated user" depends on ``PrincipalDep`` directly; a route
that needs a specific permission depends on ``require_permission(Permission.X)`` instead, which
still yields the principal.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor

from colt_api.auth import JwtVerifier, TokenVerificationError
from colt_api.errors import AuthenticationError, PolicyDeniedError
from colt_application import (
    OrganizationContext,
    OrganizationContextError,
    ResolveOrganizationContext,
)
from colt_config import Settings, get_settings
from colt_db import get_session, set_tenant_context
from colt_db.repositories import SqlAlchemyOrganizationRepository, SqlAlchemyUserDirectory
from colt_domain import Permission

# --- Settings ----------------------------------------------------------------------------


def settings_provider() -> Settings:
    """Provide process configuration. Overridable in tests via ``dependency_overrides``."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_provider)]

# --- Request identity ----------------------------------------------------------------------


def request_id_provider(request: Request) -> str:
    """The current request's correlation ID, assigned by RequestContextMiddleware."""
    request_id: str = getattr(request.state, "request_id", "")
    return request_id


RequestIdDep = Annotated[str, Depends(request_id_provider)]

# --- Database session ----------------------------------------------------------------------


async def db_session_provider() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(db_session_provider)]

# --- JWT verification ----------------------------------------------------------------------


@lru_cache(maxsize=8)
def _jwt_verifier(issuer_url: str, audience: str, jwks_cache_seconds: int) -> JwtVerifier:
    """One verifier per distinct (issuer, audience, cache TTL) — in practice one per process.

    Keyed by these primitives rather than the ``Settings``/``AuthSettings`` object itself:
    pydantic settings models are not hashable, and caching on an unhashable key is a ``TypeError``
    the moment this is actually called — caught by testing against a real token, not by
    inspection. Tests that override settings still get their own verifier, since a different
    issuer or audience produces a different cache key.
    """
    return JwtVerifier(
        issuer_url=issuer_url, audience=audience, jwks_cache_seconds=jwks_cache_seconds
    )


def jwt_verifier_provider(settings: SettingsDep) -> JwtVerifier:
    auth = settings.auth
    return _jwt_verifier(auth.issuer_url, auth.audience, auth.jwks_cache_seconds)


# ``auto_error=False``: a missing/malformed Authorization header should fail with the same
# ColtError envelope every other authentication failure uses, not FastAPI's own HTTPException.
_bearer_scheme = HTTPBearer(auto_error=False, description="A Keycloak-issued bearer JWT.")


def bearer_token_provider(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> str:
    if credentials is None:
        raise AuthenticationError("Missing or malformed Authorization header.")
    return credentials.credentials


# --- Organization context (CLAUDE.md §27, ADR-0005) ----------------------------------------


async def principal_provider(
    token: Annotated[str, Depends(bearer_token_provider)],
    verifier: Annotated[JwtVerifier, Depends(jwt_verifier_provider)],
    session: DbSessionDep,
) -> OrganizationContext:
    """Verify the bearer token, then resolve it to organization context (CLAUDE.md §27).

    Also binds ``app.current_organization_id`` on ``session`` for the rest of the request, so a
    route handler's own repository calls on this same session are RLS-protected without having
    to remember to bind it again — see ``colt_db.tenancy``.
    """
    try:
        claims = verifier.verify(token)
    except TokenVerificationError as exc:
        raise AuthenticationError("Invalid or expired credentials.") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthenticationError("Token is missing a subject claim.")

    resolve = ResolveOrganizationContext(
        SqlAlchemyUserDirectory(session), SqlAlchemyOrganizationRepository(session)
    )
    try:
        context = await resolve(subject)
    except OrganizationContextError as exc:
        raise AuthenticationError("No active user found for this identity.") from exc

    await set_tenant_context(session, context.organization.id)
    return context


PrincipalDep = Annotated[OrganizationContext, Depends(principal_provider)]


def require_permission(
    permission: Permission,
) -> Callable[[PrincipalDep], OrganizationContext]:
    """A dependency factory: ``Depends(require_permission(Permission.LEAD_WRITE))``.

    Returns the principal on success, so a route can depend on this alone rather than also
    depending on ``PrincipalDep`` separately.
    """

    def _check(principal: PrincipalDep) -> OrganizationContext:
        if not principal.user.has_permission(permission):
            raise PolicyDeniedError(f"Missing required permission: {permission.value}.")
        return principal

    return _check


# --- Temporal (Milestone 07: observability verification only) -----------------------------


async def temporal_client_provider(settings: SettingsDep) -> Client:
    """A fresh client per request, deliberately uncached.

    Not the pattern a hot-path route would want, but there is exactly one caller today
    (`POST /api/v1/observability/trace-check`, which exists to prove the trace pipeline works,
    not to be fast) and caching an async client across requests risks the same cross-event-loop
    hazards `colt_db.session`'s `NullPool` exists to avoid (see its docstring) — correctness over
    premature optimization at this stage (CLAUDE.md §105). `TracingInterceptor` propagates this
    request's trace context onto the workflow it starts.
    """
    return await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
        interceptors=[TracingInterceptor()],
    )


TemporalClientDep = Annotated[Client, Depends(temporal_client_provider)]
