"""AI Gateway error classification (CLAUDE.md §36, §68).

The Anthropic SDK already retries connection failures, 408/409/429 and >=500 with backoff
(`AnthropicSettings.max_retries`) — these classes represent what the SDK gives up on, or what
it never retries at all. `classify` maps the SDK's typed exceptions to Colt's error taxonomy so
callers can tell a permanently rejected request from one that is merely out of retries, without
string-matching provider error messages (§36.1).
"""

from __future__ import annotations

from enum import StrEnum

import anthropic


class GatewayErrorCode(StrEnum):
    """The subset of CLAUDE.md §36's error taxonomy an LLM provider call can produce."""

    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class GatewayError(Exception):
    """Base for every error `AnthropicGateway` raises.

    `retryable` reflects CLAUDE.md §36.1's policy — it is `True` only for failures the SDK's
    own retry budget may simply have been too small for (rate limits, 5xx, timeouts, network),
    never for a request a human needs to change before retrying.
    """

    def __init__(self, message: str, *, code: GatewayErrorCode, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class GatewayAuthenticationError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.AUTHENTICATION_ERROR, retryable=False)


class GatewayAuthorizationError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.AUTHORIZATION_ERROR, retryable=False)


class GatewayNotFoundError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.NOT_FOUND, retryable=False)


class GatewayRateLimitedError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.RATE_LIMITED, retryable=True)


class GatewayProviderUnavailableError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True)


class GatewayProviderRejectedError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.PROVIDER_REJECTED, retryable=False)


class GatewayTimeoutError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.TIMEOUT, retryable=True)


class GatewayDependencyFailureError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.DEPENDENCY_FAILURE, retryable=True)


class GatewayInternalError(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=GatewayErrorCode.INTERNAL_ERROR, retryable=False)


def classify(exc: anthropic.APIError) -> GatewayError:
    """Map an Anthropic SDK exception to a `GatewayError`.

    Ordered most-specific-first, per the SDK's own documented pattern: `APITimeoutError` is a
    subclass of `APIConnectionError`, and every HTTP-status error is a subclass of
    `APIStatusError`, so the narrower checks must run before the broader ones they would
    otherwise be caught by.
    """
    message = str(exc)

    if isinstance(exc, anthropic.APITimeoutError):
        return GatewayTimeoutError(message)
    if isinstance(exc, anthropic.APIConnectionError):
        return GatewayDependencyFailureError(message)

    if isinstance(exc, anthropic.AuthenticationError):
        return GatewayAuthenticationError(message)
    if isinstance(exc, anthropic.PermissionDeniedError):
        return GatewayAuthorizationError(message)
    if isinstance(exc, anthropic.NotFoundError):
        return GatewayNotFoundError(message)
    if isinstance(exc, anthropic.RateLimitError):
        return GatewayRateLimitedError(message)
    if isinstance(exc, anthropic.APIStatusError):
        # Every remaining status-coded error (409, 413, 422, 500, 529, ...) is classified by
        # status code rather than by its specific SDK subclass — §36's taxonomy only
        # distinguishes "the provider is down, try again" from "this request is permanently
        # bad," and the status code alone already answers that.
        if exc.status_code >= 500:
            return GatewayProviderUnavailableError(message)
        return GatewayProviderRejectedError(message)

    return GatewayInternalError(message)
