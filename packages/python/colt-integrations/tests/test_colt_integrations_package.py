"""Baseline import test — proves the package is installed and importable."""

import colt_integrations


def test_package_exposes_version() -> None:
    assert colt_integrations.__version__ == "0.1.0"
