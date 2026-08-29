"""Settings behaviour, including the safety invariants (CLAUDE.md §6.4, §7)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from colt_config import Environment, ModelClass, Settings, get_settings
from colt_config.settings import AnthropicSettings, SecuritySettings

#: First token of every environment variable this package reads (CLAUDE.md §7.3).
_SETTINGS_PREFIXES = frozenset(
    {
        "APP",
        "DATABASE",
        "REDIS",
        "TEMPORAL",
        "S3",
        "AUTH",
        "ANTHROPIC",
        "EMAIL",
        "CRM",
        "SEARCH",
        "ENRICHMENT",
        "OBSERVABILITY",
        "SECURITY",
        "FEATURE",
        "RATE",
    }
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Assert on declared defaults, not on whatever the developer has configured locally.

    ``env_file`` is a relative path, so running from an empty directory means no ``.env`` is
    discovered. That keeps the real constructor under test rather than a special-cased one.
    """
    for key in list(os.environ):
        if key.split("_")[0] in _SETTINGS_PREFIXES:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()


def test_defaults_are_local_and_safe() -> None:
    settings = Settings()
    assert settings.app.env is Environment.LOCAL
    assert settings.is_local and not settings.is_production
    assert not settings.feature.any_real_side_effects


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPORAL_ADDRESS", "temporal.internal:7233")
    monkeypatch.setenv("RATE_LIMIT_API_PER_MINUTE", "42")
    settings = Settings()
    assert settings.temporal.address == "temporal.internal:7233"
    assert settings.rate_limit.api_per_minute == 42


def test_secrets_are_not_exposed_by_repr_or_str() -> None:
    settings = Settings()
    assert "colt:colt" not in repr(settings.database.url)
    assert "colt:colt" not in str(settings.database.url)
    # The value is still reachable deliberately, at the point of use.
    assert settings.database.url.get_secret_value().startswith("postgresql")


@pytest.mark.parametrize("env", [Environment.LOCAL, Environment.TEST])
@pytest.mark.parametrize(
    "flag",
    ["FEATURE_REAL_EMAIL", "FEATURE_REAL_CRM", "FEATURE_REAL_CALENDAR", "FEATURE_REAL_SOCIAL"],
)
def test_real_side_effects_are_rejected_locally(
    monkeypatch: pytest.MonkeyPatch, env: Environment, flag: str
) -> None:
    """CLAUDE.md §6.4: local and test environments perform no real external side effects."""
    monkeypatch.setenv("APP_ENV", env.value)
    monkeypatch.setenv(flag, "true")
    with pytest.raises(ValidationError, match=flag):
        Settings()


def test_real_side_effects_are_allowed_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "a" * 64)
    monkeypatch.setenv("FEATURE_REAL_EMAIL", "true")
    settings = Settings()
    assert settings.feature.real_email is True


def test_production_rejects_the_example_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError, match="APP_SECRET_KEY"):
        Settings()


def test_model_class_maps_to_configured_model_id() -> None:
    anthropic = AnthropicSettings()
    assert anthropic.model_id_for(ModelClass.FAST) == anthropic.model_fast
    assert anthropic.model_id_for(ModelClass.STRATEGIC) == anthropic.model_strategic
    # Every class must resolve; a missing mapping would be a KeyError at request time.
    for model_class in ModelClass:
        assert anthropic.model_id_for(model_class)


def test_cors_origins_parse_into_a_list() -> None:
    security = SecuritySettings(cors_allowed_origins="http://a.test, http://b.test ,")
    assert security.cors_origin_list == ["http://a.test", "http://b.test"]


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
