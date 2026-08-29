"""Baseline import test — proves the package is installed and importable."""

import colt_application


def test_package_exposes_version() -> None:
    assert colt_application.__version__ == "0.1.0"
