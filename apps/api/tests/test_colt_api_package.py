"""Baseline import test — proves the package is installed and importable."""

import colt_api


def test_package_exposes_version() -> None:
    assert colt_api.__version__ == "0.1.0"
