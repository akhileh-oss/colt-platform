"""Baseline import test — proves the package is installed and importable."""

import colt_domain


def test_package_exposes_version() -> None:
    assert colt_domain.__version__ == "0.1.0"
