"""`classify` maps the Anthropic SDK's typed exceptions to Colt's error taxonomy
(CLAUDE.md §36) — most-specific-first, so a request-timeout isn't mistaken for a generic
connection failure and a 5xx isn't mistaken for a permanently bad request.
"""

from __future__ import annotations

import httpx2
import pytest
from anthropic import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from colt_ai.errors import (
    GatewayAuthenticationError,
    GatewayAuthorizationError,
    GatewayDependencyFailureError,
    GatewayErrorCode,
    GatewayNotFoundError,
    GatewayProviderRejectedError,
    GatewayProviderUnavailableError,
    GatewayRateLimitedError,
    GatewayTimeoutError,
    classify,
)

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(status_code: int, exc_cls: type[Exception]) -> Exception:
    response = httpx2.Response(status_code, request=_REQUEST)
    return exc_cls("boom", response=response, body=None)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("make_exc", "expected_cls", "expected_code", "expected_retryable"),
    [
        (
            lambda: APITimeoutError(request=_REQUEST),
            GatewayTimeoutError,
            GatewayErrorCode.TIMEOUT,
            True,
        ),
        (
            lambda: APIConnectionError(message="no route", request=_REQUEST),
            GatewayDependencyFailureError,
            GatewayErrorCode.DEPENDENCY_FAILURE,
            True,
        ),
        (
            lambda: _status_error(401, AuthenticationError),
            GatewayAuthenticationError,
            GatewayErrorCode.AUTHENTICATION_ERROR,
            False,
        ),
        (
            lambda: _status_error(403, PermissionDeniedError),
            GatewayAuthorizationError,
            GatewayErrorCode.AUTHORIZATION_ERROR,
            False,
        ),
        (
            lambda: _status_error(404, NotFoundError),
            GatewayNotFoundError,
            GatewayErrorCode.NOT_FOUND,
            False,
        ),
        (
            lambda: _status_error(429, RateLimitError),
            GatewayRateLimitedError,
            GatewayErrorCode.RATE_LIMITED,
            True,
        ),
        (
            lambda: _status_error(400, BadRequestError),
            GatewayProviderRejectedError,
            GatewayErrorCode.PROVIDER_REJECTED,
            False,
        ),
        (
            lambda: _status_error(500, InternalServerError),
            GatewayProviderUnavailableError,
            GatewayErrorCode.PROVIDER_UNAVAILABLE,
            True,
        ),
        (
            # 529 (overloaded) has no distinct SDK subclass check in `classify` — it still
            # lands on PROVIDER_UNAVAILABLE purely from `status_code >= 500`.
            lambda: _status_error(529, InternalServerError),
            GatewayProviderUnavailableError,
            GatewayErrorCode.PROVIDER_UNAVAILABLE,
            True,
        ),
    ],
)
def test_classify_maps_sdk_exception_to_gateway_error(
    make_exc: object,
    expected_cls: type[Exception],
    expected_code: GatewayErrorCode,
    expected_retryable: bool,
) -> None:
    exc = make_exc()  # type: ignore[operator]
    error = classify(exc)

    assert isinstance(error, expected_cls)
    assert error.code == expected_code
    assert error.retryable is expected_retryable
