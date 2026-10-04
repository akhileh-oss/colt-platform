"""Provider adapters implementing the domain-facing ports (CLAUDE.md §28)."""

from colt_integrations.enrichment import (
    ApolloEnrichmentProvider,
    CompanyCandidate,
    EnrichmentProvider,
    FakeEnrichmentProvider,
    PersonCandidate,
)
from colt_integrations.errors import (
    ProviderAuthenticationError,
    ProviderBlockedError,
    ProviderDependencyFailureError,
    ProviderError,
    ProviderErrorCode,
    ProviderRateLimitedError,
    ProviderRejectedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    classify_http_status,
)
from colt_integrations.fetch import FetchedDocument, FetchProvider, HttpFetchProvider, html_to_text
from colt_integrations.search import (
    BraveSearchProvider,
    FakeSearchProvider,
    SearchProvider,
    SearchResult,
)

__version__ = "0.1.0"

__all__ = [
    "ApolloEnrichmentProvider",
    "BraveSearchProvider",
    "CompanyCandidate",
    "EnrichmentProvider",
    "FakeEnrichmentProvider",
    "FakeSearchProvider",
    "FetchProvider",
    "FetchedDocument",
    "HttpFetchProvider",
    "PersonCandidate",
    "ProviderAuthenticationError",
    "ProviderBlockedError",
    "ProviderDependencyFailureError",
    "ProviderError",
    "ProviderErrorCode",
    "ProviderRateLimitedError",
    "ProviderRejectedError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "SearchProvider",
    "SearchResult",
    "__version__",
    "classify_http_status",
    "html_to_text",
]
