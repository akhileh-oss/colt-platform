"""`HttpFetchProvider`'s SSRF guard — hermetic: every case here is rejected before any network
connection is attempted, so none of it needs outbound internet access.

`tests/integration/test_research_fetch.py` separately proves the happy path against a real
public URL.
"""

from __future__ import annotations

import pytest

from colt_config import SecuritySettings
from colt_integrations.errors import ProviderBlockedError
from colt_integrations.fetch.http import HttpFetchProvider


@pytest.fixture
def provider() -> HttpFetchProvider:
    return HttpFetchProvider(SecuritySettings())


async def test_rejects_a_loopback_address(provider: HttpFetchProvider) -> None:
    with pytest.raises(ProviderBlockedError):
        await provider.fetch("http://127.0.0.1/")


async def test_rejects_localhost_by_name(provider: HttpFetchProvider) -> None:
    with pytest.raises(ProviderBlockedError):
        await provider.fetch("http://localhost/")


async def test_rejects_a_private_network_address(provider: HttpFetchProvider) -> None:
    with pytest.raises(ProviderBlockedError):
        await provider.fetch("http://10.0.0.5/")


async def test_rejects_a_link_local_address(provider: HttpFetchProvider) -> None:
    with pytest.raises(ProviderBlockedError):
        await provider.fetch("http://169.254.169.254/")  # the cloud metadata endpoint


async def test_rejects_a_disallowed_scheme(provider: HttpFetchProvider) -> None:
    with pytest.raises(ProviderBlockedError):
        await provider.fetch("file:///etc/passwd")


async def test_allows_private_networks_when_the_guard_is_disabled() -> None:
    """Proves the guard is what's blocking the cases above, not something else (DNS failure,
    connection refused) — with it off, resolution succeeds and the attempt reaches the network
    (and fails there with a *connection* error, normalized to `ProviderDependencyFailureError`,
    not the `ProviderBlockedError` the guard raises before any connection is attempted)."""
    from colt_integrations.errors import ProviderDependencyFailureError

    provider = HttpFetchProvider(SecuritySettings(block_private_networks=False))
    with pytest.raises(ProviderDependencyFailureError):
        await provider.fetch("http://127.0.0.1:1/")
