"""`SmtpEmailProvider` (CLAUDE.md §29) — real SMTP, configured by `EmailSettings`.

One class serves both this milestone's "Mailpit adapter" and "real provider adapter behind
feature flag" Build items, a deliberate, documented choice rather than two near-duplicate
classes: SMTP is the one wire protocol both targets speak — `EmailSettings.smtp_host`/`smtp_
port` point at local Mailpit by default (no auth, no TLS) and would point at a real provider's
SMTP relay with real credentials when `FEATURE_REAL_EMAIL` is on, same code path either way.
CLAUDE.md names no specific commercial email API the way it names Apollo (enrichment) or Brave
(search), so there is no vendor-specific REST shape to adapt to — the same reasoning Milestone
12 used for having no real signal-source provider beyond the port and a literal mock trigger.

Uses the standard library's `smtplib`/`email`, not a third-party async SMTP client: no new
dependency, and the blocking call is wrapped in `asyncio.to_thread` rather than made genuinely
async, since a single outbound send is not a hot path this milestone needs to optimize.
"""

from __future__ import annotations

import asyncio
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from colt_config import EmailSettings
from colt_integrations.email.port import SentEmail
from colt_integrations.errors import ProviderRejectedError, ProviderUnavailableError
from colt_observability import get_logger, get_tracer

logger = get_logger(__name__)
_tracer = get_tracer(__name__)


class SmtpEmailProvider:
    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings

    async def send(
        self,
        *,
        to_email: str,
        to_name: str | None,
        subject: str,
        body_text: str,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        unsubscribe_url: str | None = None,
    ) -> SentEmail:
        start = time.monotonic()
        with _tracer.start_as_current_span(
            "email_provider.send", attributes={"provider": self._settings.provider}
        ):
            sent = await asyncio.to_thread(
                self._send_sync,
                to_email,
                to_name,
                subject,
                body_text,
                in_reply_to,
                references,
                unsubscribe_url,
            )
            logger.info(
                "email sent",
                extra={
                    "operation": "send_email",
                    "provider": self._settings.provider,
                    "status": "ok",
                    "latency_ms": (time.monotonic() - start) * 1000,
                },
            )
            return sent

    def _send_sync(
        self,
        to_email: str,
        to_name: str | None,
        subject: str,
        body_text: str,
        in_reply_to: str | None,
        references: list[str] | None,
        unsubscribe_url: str | None,
    ) -> SentEmail:
        message_id = make_msgid(domain="colt.local")
        message = EmailMessage()
        message["From"] = formataddr((self._settings.from_name, self._settings.from_address))
        message["To"] = formataddr((to_name or "", to_email))
        message["Subject"] = subject
        message["Message-ID"] = message_id
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = " ".join(references)
        if unsubscribe_url:
            # RFC 8058 one-click unsubscribe — a header, never a body-text link the model's own
            # draft would need to know to include.
            message["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        message.set_content(body_text)

        try:
            with smtplib.SMTP(
                self._settings.smtp_host, self._settings.smtp_port, timeout=10
            ) as client:
                if self._settings.smtp_use_tls:
                    client.starttls()
                if self._settings.smtp_username:
                    client.login(
                        self._settings.smtp_username,
                        self._settings.smtp_password.get_secret_value(),
                    )
                client.send_message(message)
        except smtplib.SMTPRecipientsRefused as exc:
            raise ProviderRejectedError(f"SMTP server refused {to_email!r}: {exc}") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise ProviderUnavailableError(f"SMTP send to {to_email!r} failed: {exc}") from exc

        return SentEmail(message_id=message_id)
