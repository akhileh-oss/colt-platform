"""`HttpFetchProvider` (CLAUDE.md §28.1, §28.2): a real, SSRF-safe HTTP fetcher.

Needs no provider API key — unlike `BraveSearchProvider`, this is fully real and verifiable in
any environment with outbound internet access: fetching a public URL requires no credential.
Every setting it reads (`block_private_networks`, `http_fetch_timeout_seconds`,
`http_max_redirects`, `http_max_response_bytes`) was scaffolded onto `SecuritySettings` in
Milestone 00 and left unused until this milestone wires it up.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx

from colt_config import SecuritySettings
from colt_integrations.errors import (
    ProviderBlockedError,
    ProviderDependencyFailureError,
    ProviderRejectedError,
    ProviderTimeoutError,
    classify_http_status,
)
from colt_integrations.fetch.normalize import html_to_text
from colt_integrations.fetch.port import FetchedDocument
from colt_observability import get_logger, get_tracer

logger = get_logger(__name__)
_tracer = get_tracer(__name__)

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_CONTENT_TYPES = ("text/html", "text/plain")


async def _resolve_and_check(host: str, *, block_private_networks: bool) -> None:
    """Raise `ProviderBlockedError` if `host` resolves to a private/loopback/link-local/
    reserved address. A DNS-rebinding window remains between this check and the actual
    connection — accepted for this milestone's scope rather than pinning the resolved IP into
    the HTTP connection itself, which would need a custom transport."""
    if not block_private_networks:
        return
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ProviderBlockedError(f"could not resolve host {host!r}: {exc}") from exc

    for info in infos:
        address = info[4][0]
        parsed_ip = ipaddress.ip_address(address)
        if (
            parsed_ip.is_private
            or parsed_ip.is_loopback
            or parsed_ip.is_link_local
            or parsed_ip.is_reserved
            or parsed_ip.is_multicast
            or parsed_ip.is_unspecified
        ):
            raise ProviderBlockedError(
                f"host {host!r} resolves to a disallowed address ({address})."
            )


def _check_url(url: str, *, block_private_networks: bool) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ProviderBlockedError(f"scheme {parsed.scheme!r} is not allowed.")
    if not parsed.hostname:
        raise ProviderBlockedError("URL has no host.")
    return parsed.hostname


class HttpFetchProvider:
    def __init__(self, settings: SecuritySettings) -> None:
        self._settings = settings

    async def fetch(self, url: str) -> FetchedDocument:
        start = time.monotonic()
        with _tracer.start_as_current_span(
            "fetch_provider.fetch", attributes={"provider": "http"}
        ) as span:
            try:
                document = await self._fetch(url)
            except ProviderBlockedError:
                raise
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(f"fetching {url} timed out: {exc}") from exc
            except httpx.HTTPError as exc:
                raise ProviderDependencyFailureError(f"fetching {url} failed: {exc}") from exc

            latency_ms = (time.monotonic() - start) * 1000
            span.set_attribute("status_code", document.status_code)
            logger.info(
                "fetch completed",
                extra={
                    "operation": "fetch_page",
                    "provider": "http",
                    "status": "ok",
                    "status_code": document.status_code,
                    "latency_ms": latency_ms,
                },
            )
            return document

    async def _fetch(self, url: str) -> FetchedDocument:
        current_url = url
        async with httpx.AsyncClient(
            timeout=self._settings.http_fetch_timeout_seconds, follow_redirects=False
        ) as client:
            for _ in range(self._settings.http_max_redirects + 1):
                host = _check_url(
                    current_url, block_private_networks=self._settings.block_private_networks
                )
                await _resolve_and_check(
                    host, block_private_networks=self._settings.block_private_networks
                )

                async with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ProviderRejectedError(
                                f"{current_url} redirected with no Location header."
                            )
                        current_url = urljoin(current_url, location)
                        continue

                    if response.status_code >= 400:
                        raise classify_http_status(
                            response.status_code, f"{current_url} returned {response.status_code}"
                        )

                    body = await self._read_capped(response)
                    content_type = response.headers.get("content-type", "").split(";")[0].strip()
                    return self._to_document(
                        url, current_url, response.status_code, content_type, body
                    )

        raise ProviderRejectedError(
            f"{url}: too many redirects ({self._settings.http_max_redirects})."
        )

    async def _read_capped(self, response: httpx.Response) -> bytes:
        limit = self._settings.http_max_response_bytes
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > limit:
                raise ProviderRejectedError(
                    f"response exceeded {limit} bytes while fetching {response.url}."
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _to_document(
        self, original_url: str, final_url: str, status_code: int, content_type: str, body: bytes
    ) -> FetchedDocument:
        if content_type not in _ALLOWED_CONTENT_TYPES:
            raise ProviderRejectedError(f"unsupported content type {content_type!r}.")
        decoded = body.decode("utf-8", errors="replace")
        if content_type == "text/html":
            title, text = html_to_text(decoded)
        else:
            title, text = None, decoded.strip()
        return FetchedDocument(
            url=original_url,
            final_url=final_url,
            status_code=status_code,
            title=title,
            text=text,
            fetched_at=datetime.now(UTC),
        )
