"""`HttpFetchProvider`'s happy path, against a real public URL (CLAUDE.md §28, Milestone 10).

No provider API key is needed for this one — fetching a public webpage requires no credential,
unlike `BraveSearchProvider` (see `packages/python/colt-integrations/tests/` for that adapter's
hermetic, mocked-transport proof instead). Marked `integration` because it needs outbound
internet access, which a sandboxed unit-test run may not have.
"""

from __future__ import annotations

import pytest

from colt_config import SecuritySettings
from colt_integrations.fetch.http import HttpFetchProvider


@pytest.mark.asyncio
async def test_fetches_and_normalizes_a_real_public_page() -> None:
    provider = HttpFetchProvider(SecuritySettings())

    document = await provider.fetch("https://example.com")

    assert document.status_code == 200
    assert document.title == "Example Domain"
    assert "domain" in document.text.lower()
    assert "<" not in document.text
    assert document.final_url.startswith("https://example.com")
