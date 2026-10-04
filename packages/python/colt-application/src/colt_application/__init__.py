"""Use cases and application services coordinating domain objects and ports."""

from colt_application.campaign_state import (
    CAMPAIGN_TRANSITIONS,
    can_transition,
    validate_campaign_definition,
)
from colt_application.errors import (
    ApplicationError,
    CampaignValidationError,
    InvalidCampaignTransitionError,
    NotFoundError,
    OrganizationContextError,
)
from colt_application.identity import DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD
from colt_application.research import (
    DEFAULT_FRESHNESS_THRESHOLD_DAYS,
    determine_verification_status,
)
from colt_application.scoring import (
    DEFAULT_SCORE_WEIGHTS,
    QUALIFICATION_THRESHOLD,
    SCORE_MODEL_VERSION,
    compute_overall_score,
    determine_qualification,
    determine_reason_codes,
)
from colt_application.signals import (
    DEFAULT_SIGNAL_CONFIDENCE,
    DEFAULT_SIGNAL_FRESHNESS_THRESHOLD_DAYS,
    DEFAULT_SIGNAL_TYPE_WEIGHT,
    SIGNAL_TYPE_WEIGHTS,
    STALE_SIGNAL_DECAY_FACTOR,
    rank_signal,
)
from colt_application.use_cases.create_campaign import CreateCampaign
from colt_application.use_cases.discover_company import DiscoverCompany
from colt_application.use_cases.discover_person import DiscoverPerson
from colt_application.use_cases.enrich_company import EnrichCompany
from colt_application.use_cases.enrich_person import EnrichPerson
from colt_application.use_cases.get_campaign import GetCampaign
from colt_application.use_cases.get_lead import GetLead
from colt_application.use_cases.list_campaigns import ListCampaigns
from colt_application.use_cases.pause_campaign import PauseCampaign
from colt_application.use_cases.record_evidence import RecordEvidence
from colt_application.use_cases.record_signal import RecordSignal
from colt_application.use_cases.resolve_organization_context import (
    OrganizationContext,
    ResolveOrganizationContext,
)
from colt_application.use_cases.resume_campaign import ResumeCampaign
from colt_application.use_cases.score_lead import ScoreLead
from colt_application.use_cases.validate_campaign import ValidateCampaign

__version__ = "0.1.0"

__all__ = [
    "CAMPAIGN_TRANSITIONS",
    "DEFAULT_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD",
    "DEFAULT_SCORE_WEIGHTS",
    "DEFAULT_SIGNAL_CONFIDENCE",
    "DEFAULT_SIGNAL_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_SIGNAL_TYPE_WEIGHT",
    "QUALIFICATION_THRESHOLD",
    "SCORE_MODEL_VERSION",
    "SIGNAL_TYPE_WEIGHTS",
    "STALE_SIGNAL_DECAY_FACTOR",
    "ApplicationError",
    "CampaignValidationError",
    "CreateCampaign",
    "DiscoverCompany",
    "DiscoverPerson",
    "EnrichCompany",
    "EnrichPerson",
    "GetCampaign",
    "GetLead",
    "InvalidCampaignTransitionError",
    "ListCampaigns",
    "NotFoundError",
    "OrganizationContext",
    "OrganizationContextError",
    "PauseCampaign",
    "RecordEvidence",
    "RecordSignal",
    "ResolveOrganizationContext",
    "ResumeCampaign",
    "ScoreLead",
    "ValidateCampaign",
    "__version__",
    "can_transition",
    "compute_overall_score",
    "determine_qualification",
    "determine_reason_codes",
    "determine_verification_status",
    "rank_signal",
    "validate_campaign_definition",
]
