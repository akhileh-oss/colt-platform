"""Colt AI gateway: model routing, structured generation, and usage/cost accounting."""

from colt_ai.client import AnthropicGateway, create_client
from colt_ai.errors import (
    GatewayAuthenticationError,
    GatewayAuthorizationError,
    GatewayDependencyFailureError,
    GatewayError,
    GatewayErrorCode,
    GatewayInternalError,
    GatewayNotFoundError,
    GatewayProviderRejectedError,
    GatewayProviderUnavailableError,
    GatewayRateLimitedError,
    GatewayTimeoutError,
    classify,
)
from colt_ai.pricing import ModelPricing, estimate_cost_usd
from colt_ai.usage import GenerationResult, RawMessage, Usage

__version__ = "0.1.0"

__all__ = [
    "AnthropicGateway",
    "GatewayAuthenticationError",
    "GatewayAuthorizationError",
    "GatewayDependencyFailureError",
    "GatewayError",
    "GatewayErrorCode",
    "GatewayInternalError",
    "GatewayNotFoundError",
    "GatewayProviderRejectedError",
    "GatewayProviderUnavailableError",
    "GatewayRateLimitedError",
    "GatewayTimeoutError",
    "GenerationResult",
    "ModelPricing",
    "RawMessage",
    "Usage",
    "__version__",
    "classify",
    "create_client",
    "estimate_cost_usd",
]
