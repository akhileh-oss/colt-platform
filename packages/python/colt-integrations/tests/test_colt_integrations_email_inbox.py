"""`MailpitInboxClient` — hermetic: a real `httpx.AsyncClient` with its transport replaced by
`httpx.MockTransport`, shaped exactly like the real Mailpit REST API this module's own docstring
documents from live testing (`MessageID` unbracketed on `/message/{id}`, `In-Reply-To` only on
the separate `/message/{id}/headers` endpoint, bracketed there). The real-Mailpit proof lives in
`tests/integration`'s Milestone 17 acceptance test.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from colt_config import EmailSettings
from colt_integrations.email.inbox import MailpitInboxClient
from colt_integrations.errors import ProviderTimeoutError, ProviderUnavailableError


def _settings() -> EmailSettings:
    return EmailSettings(mailpit_api_base_url="http://mailpit:8025")


def _handler_for(
    *, listed_ids: list[str], message_body: dict[str, object], headers: dict[str, list[str]]
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/messages":
            return httpx.Response(200, json={"messages": [{"ID": i} for i in listed_ids]})
        if request.url.path.endswith("/headers"):
            return httpx.Response(200, json=headers)
        return httpx.Response(200, json=message_body)

    return handler


async def test_lists_message_ids_newest_first() -> None:
    handler = _handler_for(listed_ids=["msg-2", "msg-1"], message_body={}, headers={})
    client = MailpitInboxClient(_settings(), transport=httpx.MockTransport(handler))

    ids = await client.list_messages(limit=10)

    assert ids == ["msg-2", "msg-1"]


async def test_get_message_reads_message_id_from_the_body_and_in_reply_to_from_headers() -> None:
    handler = _handler_for(
        listed_ids=[],
        message_body={
            "ID": "msg-1",
            "MessageID": "inbound-msg-1@mailpit",
            "From": {"Address": "lead@example.com"},
            "To": [{"Address": "outbound@colt.local"}],
            "Subject": "Re: hello",
            "Text": "Sounds good.",
        },
        headers={"In-Reply-To": ["<outbound-1@colt.local>"]},
    )
    client = MailpitInboxClient(_settings(), transport=httpx.MockTransport(handler))

    message = await client.get_message("msg-1")

    assert message.id == "msg-1"
    assert message.message_id == "inbound-msg-1@mailpit"
    assert message.in_reply_to == "<outbound-1@colt.local>"
    assert message.from_address == "lead@example.com"
    assert message.to_addresses == ["outbound@colt.local"]
    assert message.subject == "Re: hello"
    assert message.text_body == "Sounds good."


async def test_get_message_tolerates_no_in_reply_to_header() -> None:
    handler = _handler_for(
        listed_ids=[],
        message_body={"ID": "msg-2", "From": {}, "To": [], "Subject": "", "Text": ""},
        headers={},
    )
    client = MailpitInboxClient(_settings(), transport=httpx.MockTransport(handler))

    message = await client.get_message("msg-2")

    assert message.in_reply_to is None
    assert message.message_id is None


async def test_a_timeout_is_classified_as_provider_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    client = MailpitInboxClient(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderTimeoutError):
        await client.list_messages()


async def test_a_5xx_response_is_classified_as_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = MailpitInboxClient(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(ProviderUnavailableError):
        await client.list_messages()
