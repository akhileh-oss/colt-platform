"""FastAPI application factory (CLAUDE.md §5.1, §25).

The composition root: it wires configuration, logging, middleware and routers together and
holds no business logic of its own.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from colt_api.errors import ErrorResponse, register_exception_handlers
from colt_api.middleware import (
    AccessLogMiddleware,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from colt_api.routers import health
from colt_api.routers.v1 import router as v1
from colt_config import Settings, get_settings
from colt_observability import configure_logging, get_logger

logger = get_logger(__name__)

DESCRIPTION = """
The Colt API.

Colt is an AI Revenue Operating System: it discovers prospects, researches them against
verifiable evidence, qualifies them, and orchestrates evidence-backed outreach.

Every failure returns the same envelope, carrying a `request_id` that correlates it with
server logs and traces.
""".strip()


def _build_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Startup. Milestones 05 and 06 open the database pool and Temporal client here and
        # register their readiness checks.
        logger.info(
            "api starting",
            extra={"operation": "startup", "environment": settings.app.env.value},
        )
        yield
        # Shutdown: stop accepting work, then release resources (CLAUDE.md §58). Pools and
        # clients are closed here as they are introduced.
        logger.info("api stopping", extra={"operation": "shutdown"})

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    A factory rather than a module-level singleton, so tests can construct an app with
    specific settings without mutating process state.
    """
    settings = settings or get_settings()

    configure_logging(
        level=settings.app.log_level,
        service_name=settings.observability.service_name,
    )

    app = FastAPI(
        title="Colt API",
        description=DESCRIPTION,
        version=__import__("colt_api").__version__,
        lifespan=_build_lifespan(settings),
        # Interactive docs are useful everywhere except production, where they widen the
        # surface for no operator benefit.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url="/openapi.json",
        responses={
            422: {"model": ErrorResponse, "description": "Validation error"},
            500: {"model": ErrorResponse, "description": "Internal error"},
        },
    )

    # Middleware runs in reverse registration order, so the request context is registered last
    # to make it outermost: everything below it, including the access log and error handlers,
    # can then see the request ID.
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.security.max_request_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(v1.router)

    return app


app = create_app()
