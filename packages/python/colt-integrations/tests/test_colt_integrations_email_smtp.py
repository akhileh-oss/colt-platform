"""`SmtpEmailProvider` — hermetic: `smtplib.SMTP` itself is replaced with a `MagicMock`, so the
constructed `EmailMessage`'s headers and the SMTP call sequence (STARTTLS, login, send) are
exercised for real with no network call and no running Mailpit. The Mailpit-backed, real-SMTP
proof lives in `tests/integration`'s Milestone 17 acceptance test.
"""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from colt_config import EmailSettings
from colt_integrations.email.smtp import SmtpEmailProvider
from colt_integrations.errors import ProviderRejectedError, ProviderUnavailableError


def _settings(**overrides: object) -> EmailSettings:
    return EmailSettings(**{"smtp_host": "mailpit", "smtp_port": 1025, **overrides})  # type: ignore[arg-type]


def _mock_smtp_class() -> tuple[MagicMock, MagicMock]:
    """A `smtplib.SMTP` class double whose context-manager `__enter__` yields the client mock
    tests assert against."""
    client = MagicMock()
    smtp_cls = MagicMock()
    smtp_cls.return_value.__enter__.return_value = client
    return smtp_cls, client


async def test_sends_a_plain_message_with_a_message_id() -> None:
    smtp_cls, client = _mock_smtp_class()
    provider = SmtpEmailProvider(_settings())

    with patch("smtplib.SMTP", smtp_cls):
        sent = await provider.send(
            to_email="lead@example.com", to_name="Lead Person", subject="Hi", body_text="Hello."
        )

    assert sent.message_id.startswith("<") and sent.message_id.endswith(">")
    (sent_message,) = [call.args[0] for call in client.send_message.call_args_list]
    assert sent_message["To"] == "Lead Person <lead@example.com>"
    assert sent_message["Subject"] == "Hi"
    assert sent_message["Message-ID"] == sent.message_id
    assert "In-Reply-To" not in sent_message
    assert "List-Unsubscribe" not in sent_message
    client.starttls.assert_not_called()
    client.login.assert_not_called()


async def test_threading_and_unsubscribe_headers_are_set_when_provided() -> None:
    smtp_cls, client = _mock_smtp_class()
    provider = SmtpEmailProvider(_settings())

    with patch("smtplib.SMTP", smtp_cls):
        await provider.send(
            to_email="lead@example.com",
            to_name=None,
            subject="Re: hi",
            body_text="Following up.",
            in_reply_to="<outbound-1@colt.local>",
            references=["<outbound-1@colt.local>"],
            unsubscribe_url="https://colt.local/unsubscribe/org/msg",
        )

    (sent_message,) = [call.args[0] for call in client.send_message.call_args_list]
    assert sent_message["In-Reply-To"] == "<outbound-1@colt.local>"
    assert sent_message["References"] == "<outbound-1@colt.local>"
    assert sent_message["List-Unsubscribe"] == "<https://colt.local/unsubscribe/org/msg>"
    assert sent_message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


async def test_tls_and_login_are_used_when_configured() -> None:
    smtp_cls, client = _mock_smtp_class()
    provider = SmtpEmailProvider(
        _settings(smtp_use_tls=True, smtp_username="relay-user", smtp_password=SecretStr("s3cr3t"))
    )

    with patch("smtplib.SMTP", smtp_cls):
        await provider.send(
            to_email="lead@example.com", to_name=None, subject="Hi", body_text="Hello."
        )

    client.starttls.assert_called_once()
    client.login.assert_called_once_with("relay-user", "s3cr3t")


async def test_a_refused_recipient_raises_provider_rejected() -> None:
    smtp_cls, client = _mock_smtp_class()
    client.send_message.side_effect = smtplib.SMTPRecipientsRefused(
        {"lead@example.com": (550, b"No such user")}
    )
    provider = SmtpEmailProvider(_settings())

    with patch("smtplib.SMTP", smtp_cls), pytest.raises(ProviderRejectedError):
        await provider.send(
            to_email="lead@example.com", to_name=None, subject="Hi", body_text="Hello."
        )


async def test_an_unreachable_server_raises_provider_unavailable() -> None:
    smtp_cls = MagicMock(side_effect=OSError("connection refused"))
    provider = SmtpEmailProvider(_settings())

    with patch("smtplib.SMTP", smtp_cls), pytest.raises(ProviderUnavailableError):
        await provider.send(
            to_email="lead@example.com", to_name=None, subject="Hi", body_text="Hello."
        )
