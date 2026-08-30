"""Organization entity invariants (CLAUDE.md §10.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from colt_domain import Organization, OrganizationStatus

NOW = datetime.now(UTC)


def _make(
    *,
    name: str = "Acme Corp",
    slug: str = "acme-corp",
    status: OrganizationStatus = OrganizationStatus.ACTIVE,
) -> Organization:
    return Organization(
        id=uuid4(), name=name, slug=slug, status=status, created_at=NOW, updated_at=NOW
    )


def test_defaults_to_active() -> None:
    assert _make().status is OrganizationStatus.ACTIVE
    assert _make().is_active


@pytest.mark.parametrize(
    "slug",
    ["Not Valid!", "UPPER-CASE", "-leading-hyphen", "trailing-hyphen-", "double--hyphen", ""],
)
def test_invalid_slugs_are_rejected(slug: str) -> None:
    with pytest.raises(ValidationError, match="slug"):
        _make(slug=slug)


@pytest.mark.parametrize("slug", ["acme", "acme-corp", "acme-corp-2", "a1b2c3"])
def test_valid_slugs_are_accepted(slug: str) -> None:
    assert _make(slug=slug).slug == slug


def test_blank_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="blank"):
        _make(name="   ")


def test_entity_is_frozen() -> None:
    org = _make()
    with pytest.raises(ValidationError):
        org.status = OrganizationStatus.ARCHIVED


def test_with_status_returns_a_new_instance() -> None:
    org = _make()
    later = datetime.now(UTC)
    archived = org.with_status(OrganizationStatus.ARCHIVED, at=later)

    assert org.status is OrganizationStatus.ACTIVE, "original must be unchanged"
    assert archived.status is OrganizationStatus.ARCHIVED
    assert archived.updated_at == later
    assert archived is not org
