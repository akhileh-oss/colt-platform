"""Typed application configuration for every Colt service (CLAUDE.md §7)."""

from colt_config.settings import (
    AnthropicSettings,
    AppSettings,
    AuthSettings,
    CRMSettings,
    DatabaseSettings,
    EmailSettings,
    EnrichmentSettings,
    Environment,
    FeatureSettings,
    ModelClass,
    ObservabilitySettings,
    RateLimitSettings,
    RedisSettings,
    S3Settings,
    SearchSettings,
    SecuritySettings,
    Settings,
    TemporalSettings,
    get_settings,
)

__version__ = "0.1.0"

__all__ = [
    "AnthropicSettings",
    "AppSettings",
    "AuthSettings",
    "CRMSettings",
    "DatabaseSettings",
    "EmailSettings",
    "EnrichmentSettings",
    "Environment",
    "FeatureSettings",
    "ModelClass",
    "ObservabilitySettings",
    "RateLimitSettings",
    "RedisSettings",
    "S3Settings",
    "SearchSettings",
    "SecuritySettings",
    "Settings",
    "TemporalSettings",
    "__version__",
    "get_settings",
]
