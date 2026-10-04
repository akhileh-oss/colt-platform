from __future__ import annotations

from datetime import UTC, date, datetime

from colt_application.research import determine_verification_status
from colt_domain import VerificationStatus

NOW = datetime(2026, 10, 4, tzinfo=UTC)


def test_a_recent_source_date_is_unverified() -> None:
    status = determine_verification_status(source_date=date(2026, 9, 1), observed_at=NOW, now=NOW)

    assert status == VerificationStatus.UNVERIFIED


def test_a_source_date_older_than_the_threshold_is_stale() -> None:
    status = determine_verification_status(source_date=date(2025, 1, 1), observed_at=NOW, now=NOW)

    assert status == VerificationStatus.STALE


def test_falls_back_to_observed_at_when_source_date_is_unknown() -> None:
    old_observed_at = datetime(2025, 1, 1, tzinfo=UTC)

    status = determine_verification_status(source_date=None, observed_at=old_observed_at, now=NOW)

    assert status == VerificationStatus.STALE


def test_a_custom_freshness_threshold_is_respected() -> None:
    status = determine_verification_status(
        source_date=date(2026, 9, 1), observed_at=NOW, now=NOW, freshness_threshold_days=10
    )

    assert status == VerificationStatus.STALE
