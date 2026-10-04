"""Enrichment provider port and adapters (CLAUDE.md §28)."""

from colt_integrations.enrichment.apollo import ApolloEnrichmentProvider
from colt_integrations.enrichment.fake import FakeEnrichmentProvider
from colt_integrations.enrichment.port import CompanyCandidate, EnrichmentProvider, PersonCandidate

__all__ = [
    "ApolloEnrichmentProvider",
    "CompanyCandidate",
    "EnrichmentProvider",
    "FakeEnrichmentProvider",
    "PersonCandidate",
]
