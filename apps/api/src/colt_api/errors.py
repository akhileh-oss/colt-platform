"""Error taxonomy and structured error responses (CLAUDE.md §25.4, §36).

Every failure leaving the API has the same machine-readable shape and carries the request ID,
so a user-visible failure can always be traced to one request (§92).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from colt_observability import get_logger, get_request_id

logger = get_logger(__name__)


class ErrorCode(StrEnum):
    """The error classification required by CLAUDE.md §36."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    POLICY_DENIED = "POLICY_DENIED"


_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.AUTHENTICATION_ERROR: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.AUTHORIZATION_ERROR: status.HTTP_403_FORBIDDEN,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.PROVIDER_UNAVAILABLE: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.PROVIDER_REJECTED: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    ErrorCode.DEPENDENCY_FAILURE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.POLICY_DENIED: status.HTTP_403_FORBIDDEN,
}

_CODE_BY_STATUS: dict[int, ErrorCode] = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.VALIDATION_ERROR,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.AUTHENTICATION_ERROR,
    status.HTTP_403_FORBIDDEN: ErrorCode.AUTHORIZATION_ERROR,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    status.HTTP_413_CONTENT_TOO_LARGE: ErrorCode.VALIDATION_ERROR,
    status.HTTP_422_UNPROCESSABLE_CONTENT: ErrorCode.VALIDATION_ERROR,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
    status.HTTP_502_BAD_GATEWAY: ErrorCode.PROVIDER_UNAVAILABLE,
    status.HTTP_503_SERVICE_UNAVAILABLE: ErrorCode.DEPENDENCY_FAILURE,
    status.HTTP_504_GATEWAY_TIMEOUT: ErrorCode.TIMEOUT,
}


class ErrorDetail(BaseModel):
    code: ErrorCode = Field(description="Machine-readable error classification.")
    message: str = Field(description="Human-readable description. Safe to surface to a user.")
    request_id: str | None = Field(
        default=None, description="Correlates this failure with server logs and traces."
    )
    details: dict[str, Any] | None = Field(
        default=None, description="Structured context. Never contains secrets or stack traces."
    )


class ErrorResponse(BaseModel):
    """The single error envelope every failing endpoint returns (CLAUDE.md §25.4)."""

    error: ErrorDetail


class ColtError(Exception):
    """An application error that maps to a classified HTTP response.

    Raise this rather than ``HTTPException`` so the code, status and body stay consistent.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code or _STATUS_BY_CODE[code]


class NotFoundError(ColtError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, **kwargs)


class ValidationError(ColtError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, **kwargs)


class ConflictError(ColtError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(ErrorCode.CONFLICT, message, **kwargs)


class PolicyDeniedError(ColtError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(ErrorCode.POLICY_DENIED, message, **kwargs)


class RateLimitedError(ColtError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(ErrorCode.RATE_LIMITED, message, **kwargs)


class AuthenticationError(ColtError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(ErrorCode.AUTHENTICATION_ERROR, message, **kwargs)


def _resolve_request_id(request: Request) -> str | None:
    """Find the request ID for an error body.

    The request scope is checked before the logging context because Starlette runs the
    handler for an unhandled ``Exception`` inside ``ServerErrorMiddleware``, which sits
    *outside* our middleware stack: by then the context var has already unwound. Reading it
    from the scope keeps a request ID on 500s, which are the responses that most need one
    (CLAUDE.md §92).
    """
    scoped: str | None = getattr(request.state, "request_id", None)
    return scoped or get_request_id()


def _error_response(
    request: Request,
    code: ErrorCode,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code=code, message=message, request_id=_resolve_request_id(request), details=details
        )
    )
    response = JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
    # Echo the header too: the middleware that normally does so is not in the path for an
    # unhandled exception.
    request_id = _resolve_request_id(request)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers so every failure returns the §25.4 envelope."""

    @app.exception_handler(ColtError)
    async def _handle_colt_error(request: Request, exc: ColtError) -> JSONResponse:
        logger.warning(
            "request failed",
            extra={"error_code": exc.code.value, "status": exc.status_code},
        )
        return _error_response(request, exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's own error list is safe to return: it describes the caller's input shape.
        return _error_response(
            request,
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"errors": [{k: v for k, v in e.items() if k != "ctx"} for e in exc.errors()]},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODE_BY_STATUS.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return _error_response(request, code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the type for operators; never return it. The client gets a request ID and
        # nothing that describes our internals (§25.4).
        logger.exception(
            "unhandled exception", extra={"error_code": ErrorCode.INTERNAL_ERROR.value}
        )
        return _error_response(
            request,
            ErrorCode.INTERNAL_ERROR,
            "An unexpected error occurred.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
