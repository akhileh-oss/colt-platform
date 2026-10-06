"""Email provider port and adapters (CLAUDE.md §29)."""

from colt_integrations.email.inbox import InboxMessage, MailpitInboxClient
from colt_integrations.email.message_sender import EmailMessageSender
from colt_integrations.email.port import EmailProvider, SentEmail
from colt_integrations.email.smtp import SmtpEmailProvider

__all__ = [
    "EmailMessageSender",
    "EmailProvider",
    "InboxMessage",
    "MailpitInboxClient",
    "SentEmail",
    "SmtpEmailProvider",
]
