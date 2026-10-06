"""`MailpitInboxClient` — reads mail back out of local Mailpit through its own REST API
(CLAUDE.md §29: "Use local Mailpit during development"), never a real provider's inbound
webhook (no real provider is configured in this environment). This is what both inbound
processing and this milestone's own acceptance test use to prove a send actually landed and a
reply can be read back, entirely over the local Docker network.

Verified live against a real Mailpit instance, not guessed: `GET /api/v1/message/{id}` carries
`MessageID` *without* angle brackets at the top level, but has no `In-Reply-To` field at all —
that only appears, with brackets, through the separate `GET /api/v1/message/{id}/headers`
endpoint. `in_reply_to` is the one field this client reads from there, kept bracketed so it
compares equal to `Message.provider_message_id`, which `SmtpEmailProvider` also stores bracketed
(`email.utils.make_msgid()`'s own format) — the two sides of §29.1's threading match must agree
on this, not each normalize it differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from colt_config import EmailSettings
from colt_integrations.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    classify_http_status,
)


@dataclass(frozen=True, slots=True)
class InboxMessage:
    id: str
    message_id: str | None
    in_reply_to: str | None
    from_address: str
    to_addresses: list[str]
    subject: str
    text_body: str


class MailpitInboxClient:
    def __init__(
        self, settings: EmailSettings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def list_messages(self, *, limit: int = 50) -> list[str]:
        """Return the ids of the most recently received messages, newest first."""
        body = await self._get("/api/v1/messages", params={"limit": limit})
        return [item["ID"] for item in body.get("messages", [])]

    async def get_message(self, message_id: str) -> InboxMessage:
        body = await self._get(f"/api/v1/message/{message_id}")
        headers = await self._get(f"/api/v1/message/{message_id}/headers")
        return InboxMessage(
            id=body["ID"],
            message_id=body.get("MessageID"),
            in_reply_to=_first_header(headers, "In-Reply-To"),
            from_address=body.get("From", {}).get("Address", ""),
            to_addresses=[to.get("Address", "") for to in body.get("To", [])],
            subject=body.get("Subject", ""),
            text_body=body.get("Text", ""),
        )

    async def _get(self, path: str, *, params: dict[str, int] | None = None) -> dict[str, Any]:
        url = f"{self._settings.mailpit_api_base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                response = await client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Mailpit request to {url!r} timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Mailpit request to {url!r} failed: {exc}") from exc

        if response.status_code >= 400:
            raise classify_http_status(
                response.status_code, f"Mailpit returned {response.status_code} for {url!r}"
            )
        body: dict[str, Any] = response.json()
        return body


def _first_header(headers: dict[str, Any], name: str) -> str | None:
    values = headers.get(name) or []
    return values[0] if values else None
