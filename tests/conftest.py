"""Shared pytest configuration for the Colt test suites.

Suite layout (CLAUDE.md §45):

- ``tests/unit``         pure logic, no I/O
- ``tests/integration``  requires local infrastructure
- ``tests/e2e``          drives the running application
- ``tests/workflows``    Temporal workflow tests
- ``tests/security``     security and tenant-isolation invariants
- ``tests/evals``        AI evaluation suites

Markers are declared in ``pyproject.toml``. Each suite directory applies its own marker
automatically via the mapping below, so a suite can be selected with ``-m <marker>``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SUITE_MARKERS = {
    "integration": "integration",
    "e2e": "e2e",
    "workflows": "workflows",
    "security": "security",
    "evals": "evals",
}

_TESTS_ROOT = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply the suite marker implied by each test's directory."""
    for item in items:
        try:
            relative = Path(item.path).relative_to(_TESTS_ROOT)
        except ValueError:
            continue
        suite = relative.parts[0] if relative.parts else ""
        marker = _SUITE_MARKERS.get(suite)
        if marker is not None:
            item.add_marker(getattr(pytest.mark, marker))
