"""Provider error normalization (CLAUDE.md §28.1, §36) — shared across every adapter in this
package, the same way `colt_ai.errors.classify` gives every Anthropic SDK exception one shared
taxonomy rather than letting each call site invent its own.
"""

from __future__ import annotations

from enum import StrEnum


class ProviderErrorCode(StrEnum):
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    BLOCKED = "BLOCKED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ProviderError(Exception):
    """Base for every error a provider adapter in this package raises."""

    def __init__(self, message: str, *, code: ProviderErrorCode, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ProviderAuthenticationError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=ProviderErrorCode.AUTHENTICATION_ERROR, retryable=False)


class ProviderRateLimitedError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=ProviderErrorCode.RATE_LIMITED, retryable=True)


class ProviderUnavailableError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=ProviderErrorCode.PROVIDER_UNAVAILABLE, retryable=True)


class ProviderRejectedError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=ProviderErrorCode.PROVIDER_REJECTED, retryable=False)


class ProviderTimeoutError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=ProviderErrorCode.TIMEOUT, retryable=True)


class ProviderDependencyFailureError(ProviderError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=ProviderErrorCode.DEPENDENCY_FAILURE, retryable=True)


class ProviderBlockedError(ProviderError):
    """The request was refused before it ever reached the provider — an SSRF guard rejecting a
    private/loopback/link-local target, for example. Never retryable: retrying sends the exact
    same disallowed request again."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code=ProviderErrorCode.BLOCKED, retryable=False)


def classify_http_status(status_code: int, message: str) -> ProviderError:
    """Map an HTTP status code to a `ProviderError`, the same status-code-driven classification
    `colt_ai.errors.classify` applies to the Anthropic SDK's typed exceptions."""
    if status_code == 401 or status_code == 403:
        return ProviderAuthenticationError(message)
    if status_code == 404:
        return ProviderError(message, code=ProviderErrorCode.NOT_FOUND, retryable=False)
    if status_code == 429:
        return ProviderRateLimitedError(message)
    if status_code >= 500:
        return ProviderUnavailableError(message)
    return ProviderRejectedError(message)
