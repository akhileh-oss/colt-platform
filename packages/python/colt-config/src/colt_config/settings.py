"""Typed application configuration (CLAUDE.md §7).

One settings model per §7.3 category, composed into a single :class:`Settings` aggregate.
Environment variables are read here and nowhere else in the codebase.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environments (CLAUDE.md §7.1)."""

    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class ModelClass(StrEnum):
    """Model routing classes (CLAUDE.md §14.1).

    Business code selects a class; configuration maps the class to a provider model ID, so a
    model change is a deployment change rather than a code rewrite (§14.2).
    """

    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    STRATEGIC = "strategic"


_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    case_sensitive=False,
)


class AppSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="APP_")

    env: Environment = Environment.LOCAL
    name: str = "colt"
    debug: bool = False
    log_level: str = "INFO"
    base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"
    secret_key: SecretStr = SecretStr("change-me-generate-a-random-32-byte-hex-value")


class DatabaseSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="DATABASE_")

    #: The running application connects with this — a restricted role that can read and write
    #: rows but cannot alter schema, and critically is not a Postgres superuser: a superuser
    #: bypasses Row-Level Security unconditionally, which would make every RLS policy in this
    #: repository silent dead code (CLAUDE.md §9.7, ADR-0005).
    url: SecretStr = SecretStr("postgresql+asyncpg://colt_app:colt_app@localhost:5432/colt")
    #: Alembic connects with this instead — a role with DDL privileges, used for nothing else.
    #: Least-privilege boundary, not a convenience default (CLAUDE.md §40): the app never runs
    #: with schema-altering credentials, even accidentally.
    migration_url: SecretStr = SecretStr("postgresql+asyncpg://colt:colt@localhost:5432/colt")
    echo: bool = False


class RedisSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="REDIS_")

    url: SecretStr = SecretStr("redis://localhost:6379/0")


class TemporalSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="TEMPORAL_")

    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "colt-main"


class S3Settings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="S3_")

    endpoint_url: str = "http://localhost:9000"
    region: str = "us-east-1"
    bucket_research: str = "colt-research"
    access_key_id: SecretStr = SecretStr("minioadmin")
    secret_access_key: SecretStr = SecretStr("minioadmin")
    use_path_style: bool = True


class AuthSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="AUTH_")

    issuer_url: str = "http://localhost:8081/realms/colt"
    client_id: str = "colt-api"
    client_secret: SecretStr = SecretStr("colt-api-secret")
    audience: str = "colt-api"
    jwks_cache_seconds: int = Field(default=300, ge=0)


class AnthropicSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="ANTHROPIC_")

    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    model_fast: str = "claude-haiku-4-5-20251001"
    model_standard: str = "claude-sonnet-5"
    model_deep: str = "claude-opus-5"
    model_strategic: str = "claude-opus-5"

    def model_id_for(self, model_class: ModelClass) -> str:
        """Resolve a routing class to a configured provider model ID (CLAUDE.md §14.1)."""
        return {
            ModelClass.FAST: self.model_fast,
            ModelClass.STANDARD: self.model_standard,
            ModelClass.DEEP: self.model_deep,
            ModelClass.STRATEGIC: self.model_strategic,
        }[model_class]


class EmailSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="EMAIL_")

    provider: str = "mailpit"
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, gt=0, le=65535)
    from_address: str = "outbound@example.test"
    from_name: str = "Colt"
    api_key: SecretStr = SecretStr("")


class CRMSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="CRM_")

    provider: str = "fake"
    api_key: SecretStr = SecretStr("")
    base_url: str = ""


class SearchSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="SEARCH_")

    provider: str = "fake"
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=20.0, gt=0)
    max_retries: int = Field(default=2, ge=0)


class EnrichmentSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="ENRICHMENT_")

    provider: str = "fake"
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=20.0, gt=0)
    max_retries: int = Field(default=2, ge=0)


class ObservabilitySettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="OBSERVABILITY_")

    otel_endpoint: str = "http://localhost:4317"
    service_name: str = "colt-api"
    trace_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    sentry_dsn: SecretStr = SecretStr("")
    metrics_enabled: bool = True


class SecuritySettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="SECURITY_")

    cors_allowed_origins: str = "http://localhost:3000"
    max_request_bytes: int = Field(default=1_048_576, gt=0)
    http_fetch_timeout_seconds: float = Field(default=15.0, gt=0)
    http_max_redirects: int = Field(default=3, ge=0)
    http_max_response_bytes: int = Field(default=5_242_880, gt=0)
    block_private_networks: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list. A bare '*' is never expanded into a wildcard here."""
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


class FeatureSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="FEATURE_")

    real_email: bool = False
    real_crm: bool = False
    real_calendar: bool = False
    real_social: bool = False
    outbound_enabled: bool = False
    agents_enabled: bool = True
    #: §51's own example flag. Off everywhere by default — "never turn on an external
    #: side-effect feature implicitly" — an operator opts a specific organization's campaign
    #: into auto-approval (`Campaign.approval_policy`) only once this is explicitly enabled.
    auto_approval_enabled: bool = False

    @property
    def any_real_side_effects(self) -> bool:
        return self.real_email or self.real_crm or self.real_calendar or self.real_social


class RateLimitSettings(BaseSettings):
    model_config = _CONFIG | SettingsConfigDict(env_prefix="RATE_LIMIT_")

    api_per_minute: int = Field(default=120, gt=0)
    outbound_per_org_per_day: int = Field(default=200, ge=0)
    outbound_per_org_per_hour: int = Field(default=50, ge=0)
    agent_runs_per_org_per_hour: int = Field(default=500, ge=0)


class Settings(BaseSettings):
    """The complete Colt configuration (CLAUDE.md §7.3)."""

    model_config = _CONFIG

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    crm: CRMSettings = Field(default_factory=CRMSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    feature: FeatureSettings = Field(default_factory=FeatureSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    @property
    def is_production(self) -> bool:
        return self.app.env is Environment.PRODUCTION

    @property
    def is_local(self) -> bool:
        return self.app.env is Environment.LOCAL

    @model_validator(mode="after")
    def _forbid_real_side_effects_outside_deployed_environments(self) -> Self:
        """Local and test environments must perform no real external side effects (§6.4).

        Enforced here rather than only in tooling, so that any process reading this
        configuration — API, worker, script — fails at startup instead of at first send.
        """
        if (
            self.app.env in (Environment.LOCAL, Environment.TEST)
            and self.feature.any_real_side_effects
        ):
            enabled = [
                name
                for name, on in (
                    ("FEATURE_REAL_EMAIL", self.feature.real_email),
                    ("FEATURE_REAL_CRM", self.feature.real_crm),
                    ("FEATURE_REAL_CALENDAR", self.feature.real_calendar),
                    ("FEATURE_REAL_SOCIAL", self.feature.real_social),
                )
                if on
            ]
            raise ValueError(
                f"{', '.join(enabled)} enabled while APP_ENV={self.app.env}. "
                "Local and test environments must not perform real external side effects "
                "(CLAUDE.md §6.4)."
            )
        return self

    @model_validator(mode="after")
    def _require_a_real_secret_key_in_production(self) -> Self:
        """A deployed environment must not run on the example signing key (§7.2)."""
        if self.app.env in (Environment.STAGING, Environment.PRODUCTION):
            key = self.app.secret_key.get_secret_value()
            if not key or key.startswith("change-me"):
                raise ValueError(
                    f"APP_SECRET_KEY is unset or still the example value while APP_ENV="
                    f"{self.app.env}. Generate one per environment (CLAUDE.md §7.2)."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, constructed once.

    Cached, so tests that change the environment must call ``get_settings.cache_clear()``.
    """
    return Settings()
