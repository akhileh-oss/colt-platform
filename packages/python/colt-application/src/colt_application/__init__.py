"""Use cases and application services coordinating domain objects and ports."""

from colt_application.errors import ApplicationError, NotFoundError, OrganizationContextError
from colt_application.identity import DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD
from colt_application.research import (
    DEFAULT_FRESHNESS_THRESHOLD_DAYS,
    determine_verification_status,
)
from colt_application.signals import (
    DEFAULT_SIGNAL_CONFIDENCE,
    DEFAULT_SIGNAL_FRESHNESS_THRESHOLD_DAYS,
    DEFAULT_SIGNAL_TYPE_WEIGHT,
    SIGNAL_TYPE_WEIGHTS,
    STALE_SIGNAL_DECAY_FACTOR,
    rank_signal,
)
from colt_application.use_cases.discover_company import DiscoverCompany
from colt_application.use_cases.discover_person import DiscoverPerson
from colt_application.use_cases.enrich_company import EnrichCompany
from colt_application.use_cases.enrich_person import EnrichPerson
from colt_application.use_cases.get_lead import GetLead
from colt_application.use_cases.record_evidence import RecordEvidence
from colt_application.use_cases.record_signal import RecordSignal
from colt_application.use_cases.resolve_organization_context import (
    OrganizationContext,
    ResolveOrganizationContext,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD",
    "DEFAULT_SIGNAL_CONFIDENCE",
    "DEFAULT_SIGNAL_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_SIGNAL_TYPE_WEIGHT",
    "SIGNAL_TYPE_WEIGHTS",
    "STALE_SIGNAL_DECAY_FACTOR",
    "ApplicationError",
    "DiscoverCompany",
    "DiscoverPerson",
    "EnrichCompany",
    "EnrichPerson",
    "GetLead",
    "NotFoundError",
    "OrganizationContext",
    "OrganizationContextError",
    "RecordEvidence",
    "RecordSignal",
    "ResolveOrganizationContext",
    "__version__",
    "determine_verification_status",
    "rank_signal",
]
