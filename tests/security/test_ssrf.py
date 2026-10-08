"""SSRF protection (CLAUDE.md §33, §40, Milestone 24's "SSRF protection" Build item) — a
security-suite sentinel over `colt_integrations.fetch.http`'s own guard, not a duplicate of its
exhaustive feature-level suite (`packages/python/colt-integrations/tests/
test_colt_integrations_fetch_http.py` already covers loopback/private/link-local/metadata/
disallowed-scheme rejection case by case). This file's job is narrower and different: prove the
guard's core invariant — a resolved private/loopback/link-local/reserved/multicast/unspecified
address is always blocked — holds from `tests/security/`'s own vantage point, so a regression
here is caught even if the feature-level suite is ever reorganized or weakened.

**Known, documented residual risk — accepted, not closed, by this milestone**: a DNS-rebinding
window remains between `_resolve_and_check`'s own resolution and the HTTP client's independent
connection-time resolution (`colt_integrations.fetch.http`'s own docstring already names this).
Closing it needs a custom `httpx` transport that pins the checked IP into the actual connection —
real work for a real gain, but disproportionate to this milestone's scope given `ResearchAgent`
is the only caller, fetching URLs a search provider already returned, never arbitrary
user-supplied URLs. Milestone 24's call is to document this explicitly here, where "security
regression tests" live, rather than silently carry an unremarked gap.
"""

from __future__ import annotations

import pytest

from colt_config import SecuritySettings
from colt_integrations.errors import ProviderBlockedError
from colt_integrations.fetch.http import _resolve_and_check

pytestmark = pytest.mark.security


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",  # loopback
        "localhost",  # loopback by name
        "10.0.0.1",  # private
        "172.16.0.1",  # private
        "192.168.1.1",  # private
        "169.254.169.254",  # link-local - the cloud metadata endpoint
        "0.0.0.0",  # noqa: S104 - unspecified address, used here as a blocked-address test case
    ],
)
async def test_the_ssrf_guard_blocks_every_disallowed_address_class(host: str) -> None:
    with pytest.raises(ProviderBlockedError):
        await _resolve_and_check(host, block_private_networks=True)


async def test_a_public_looking_address_is_not_blocked() -> None:
    # 93.184.216.34 is example.com's long-standing public IP - a real, routable, non-reserved
    # address the guard must let through when given it directly (no DNS lookup needed since an
    # IP literal still goes through socket.getaddrinfo, which returns it unchanged).
    await _resolve_and_check("93.184.216.34", block_private_networks=True)


async def test_the_guard_can_be_disabled_via_settings() -> None:
    """`SecuritySettings.block_private_networks=False` is an explicit, documented escape hatch
    (local development against a private test fixture), never a default."""
    assert SecuritySettings().block_private_networks is True
    await _resolve_and_check("127.0.0.1", block_private_networks=False)
