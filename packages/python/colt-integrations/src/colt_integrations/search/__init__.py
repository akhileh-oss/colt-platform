"""Search provider port and adapters (CLAUDE.md §28)."""

from colt_integrations.search.brave import BraveSearchProvider
from colt_integrations.search.fake import FakeSearchProvider
from colt_integrations.search.port import SearchProvider, SearchResult

__all__ = ["BraveSearchProvider", "FakeSearchProvider", "SearchProvider", "SearchResult"]
