"""Fetch provider port and adapters (CLAUDE.md §28)."""

from colt_integrations.fetch.http import HttpFetchProvider
from colt_integrations.fetch.normalize import html_to_text
from colt_integrations.fetch.port import FetchedDocument, FetchProvider

__all__ = ["FetchProvider", "FetchedDocument", "HttpFetchProvider", "html_to_text"]
