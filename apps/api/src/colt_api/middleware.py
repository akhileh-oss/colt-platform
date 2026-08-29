"""Base middleware: request identity, access logging, security headers, body limits.

Order matters. Request ID is outermost so that every other layer — including the access log and
any error response — can see it (CLAUDE.md §92).
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from colt_observability import bind_log_context, get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER: Final = "X-Request-ID"

#: Sent on every response (CLAUDE.md §40). HSTS is deliberately absent: it is added at the TLS
#: terminator in deployed environments, and setting it over plain HTTP locally would poison the
#: developer's browser for localhost.
SECURITY_HEADERS: Final[dict[str, str]] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

_Next = Callable[[Request], Awaitable[Response]]


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request ID, bind it to the logging context, and echo it back.

    An inbound ``X-Request-ID`` is honoured so a trace can span services, but only when it is
    already safe. The header reaches log output, so a malformed value is *replaced* rather than
    cleaned up: salvaging part of a hostile string would splice attacker-chosen text into logs
    under a header the operator believes is trustworthy.
    """

    _SAFE_REQUEST_ID: Final = re.compile(r"\A[A-Za-z0-9_-]{1,128}\Z")

    async def dispatch(self, request: Request, call_next: _Next) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = inbound if self._SAFE_REQUEST_ID.fullmatch(inbound) else _new_request_id()

        with bind_log_context(request_id=request_id):
            request.state.request_id = request_id
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Emit one structured line per request (CLAUDE.md §35)."""

    async def dispatch(self, request: Request, call_next: _Next) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request errored",
                extra={
                    "operation": f"{request.method} {request.url.path}",
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "status": 500,
                },
            )
            raise

        logger.info(
            "request completed",
            extra={
                "operation": f"{request.method} {request.url.path}",
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response (CLAUDE.md §40)."""

    async def dispatch(self, request: Request, call_next: _Next) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies (CLAUDE.md §40).

    Checks the declared Content-Length. A chunked request without one is not rejected here;
    that bound belongs at the ingress/server layer, which sees the bytes as they arrive.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: _Next) -> Response:
        declared = request.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > self._max_bytes:
            # Built here rather than raised, so the envelope matches §25.4 without importing
            # the error module into middleware.
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Request body exceeds the {self._max_bytes} byte limit.",
                        "request_id": getattr(request.state, "request_id", None),
                        "details": {"max_bytes": self._max_bytes, "received_bytes": int(declared)},
                    }
                },
            )
        return await call_next(request)
