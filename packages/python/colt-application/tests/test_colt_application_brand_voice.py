"""`get_brand_voice` (CLAUDE.md §68 Milestone 15's "brand voice config" Build item)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from colt_application.brand_voice import DEFAULT_BRAND_VOICE, get_brand_voice
from colt_domain import Organization

NOW = datetime.now(UTC)


def _organization(**settings: object) -> Organization:
    return Organization(
        id=uuid4(), name="Acme", slug="acme", settings=settings, created_at=NOW, updated_at=NOW
    )


def test_returns_the_default_when_nothing_is_configured() -> None:
    assert get_brand_voice(_organization()) == DEFAULT_BRAND_VOICE


def test_returns_the_configured_brand_voice_when_present() -> None:
    custom = {"tone": "Playful but credible.", "avoid": ["jargon"]}
    assert get_brand_voice(_organization(brand_voice=custom)) == custom


def test_falls_back_to_the_default_when_the_configured_value_is_not_a_dict() -> None:
    assert get_brand_voice(_organization(brand_voice="not a dict")) == DEFAULT_BRAND_VOICE
