"""Use cases and application services coordinating domain objects and ports."""

from colt_application.agent_cost import AgentCostRow, summarize_agent_cost
from colt_application.brand_voice import DEFAULT_BRAND_VOICE, get_brand_voice
from colt_application.campaign_state import (
    CAMPAIGN_TRANSITIONS,
    can_transition,
    validate_campaign_definition,
)
from colt_application.channel_performance import (
    ChannelPerformanceRow,
    summarize_channel_performance,
)
from colt_application.errors import (
    ApplicationError,
    CampaignValidationError,
    InvalidApprovalTransitionError,
    InvalidCampaignTransitionError,
    InvalidOpportunityTransitionError,
    MessageValidationError,
    NotFoundError,
    OrganizationContextError,
    PolicyDeniedError,
)
from colt_application.funnel import FunnelStageSummary, summarize_funnel
from colt_application.icp_performance import IcpPerformanceRow, summarize_icp_performance
from colt_application.identity import DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD
from colt_application.message_performance import (
    MessagePerformanceRow,
    summarize_message_performance,
)
from colt_application.model_performance import ModelPerformanceRow, summarize_model_performance
from colt_application.opportunity_state import OPPORTUNITY_TRANSITIONS, can_transition_stage
from colt_application.pipeline_summary import PipelineStageSummary, summarize_pipeline
from colt_application.reply_classification import Urgency, determine_conversation_transition
from colt_application.research import (
    DEFAULT_FRESHNESS_THRESHOLD_DAYS,
    determine_verification_status,
)
from colt_application.revenue_attribution import RevenueAttributionRow, summarize_revenue_by_source
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
from colt_application.trigger_performance import (
    TriggerPerformanceRow,
    summarize_trigger_performance,
)
from colt_application.use_cases.add_sequence_step import AddSequenceStep
from colt_application.use_cases.add_suppression_entry import AddSuppressionEntry
from colt_application.use_cases.assign_opportunity_owner import AssignOpportunityOwner
from colt_application.use_cases.create_campaign import CreateCampaign
from colt_application.use_cases.create_or_update_opportunity import (
    CreateOrUpdateOpportunity,
    OpportunityUpsertResult,
)
from colt_application.use_cases.decide_message_approval import DecideMessageApproval
from colt_application.use_cases.discover_company import DiscoverCompany
from colt_application.use_cases.discover_person import DiscoverPerson
from colt_application.use_cases.draft_message import DraftMessage
from colt_application.use_cases.enrich_company import EnrichCompany
from colt_application.use_cases.enrich_person import EnrichPerson
from colt_application.use_cases.get_campaign import GetCampaign
from colt_application.use_cases.get_lead import GetLead
from colt_application.use_cases.list_campaigns import ListCampaigns
from colt_application.use_cases.list_evidence_for_lead import ListEvidenceForLead
from colt_application.use_cases.list_messages import ListMessages
from colt_application.use_cases.list_sequence_steps import ListSequenceSteps
from colt_application.use_cases.pause_campaign import PauseCampaign
from colt_application.use_cases.process_bounce import ProcessBounce
from colt_application.use_cases.process_inbound_email import ProcessInboundEmail
from colt_application.use_cases.record_crm_sync_outcome import RecordCrmSyncOutcome
from colt_application.use_cases.record_evidence import RecordEvidence
from colt_application.use_cases.record_reply_classification import RecordReplyClassification
from colt_application.use_cases.record_signal import RecordSignal
from colt_application.use_cases.resolve_organization_context import (
    OrganizationContext,
    ResolveOrganizationContext,
)
from colt_application.use_cases.resume_campaign import ResumeCampaign
from colt_application.use_cases.score_lead import ScoreLead
from colt_application.use_cases.select_personalization_evidence import (
    SelectPersonalizationEvidence,
)
from colt_application.use_cases.send_message import SendMessage
from colt_application.use_cases.transition_opportunity_stage import TransitionOpportunityStage
from colt_application.use_cases.unsubscribe_by_token import UnsubscribeByToken
from colt_application.use_cases.validate_campaign import ValidateCampaign

__version__ = "0.1.0"

__all__ = [
    "CAMPAIGN_TRANSITIONS",
    "DEFAULT_BRAND_VOICE",
    "DEFAULT_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD",
    "DEFAULT_SCORE_WEIGHTS",
    "DEFAULT_SIGNAL_CONFIDENCE",
    "DEFAULT_SIGNAL_FRESHNESS_THRESHOLD_DAYS",
    "DEFAULT_SIGNAL_TYPE_WEIGHT",
    "OPPORTUNITY_TRANSITIONS",
    "QUALIFICATION_THRESHOLD",
    "SCORE_MODEL_VERSION",
    "SIGNAL_TYPE_WEIGHTS",
    "STALE_SIGNAL_DECAY_FACTOR",
    "AddSequenceStep",
    "AddSuppressionEntry",
    "AgentCostRow",
    "ApplicationError",
    "AssignOpportunityOwner",
    "CampaignValidationError",
    "ChannelPerformanceRow",
    "CreateCampaign",
    "CreateOrUpdateOpportunity",
    "DecideMessageApproval",
    "DiscoverCompany",
    "DiscoverPerson",
    "DraftMessage",
    "EnrichCompany",
    "EnrichPerson",
    "FunnelStageSummary",
    "GetCampaign",
    "GetLead",
    "IcpPerformanceRow",
    "InvalidApprovalTransitionError",
    "InvalidCampaignTransitionError",
    "InvalidOpportunityTransitionError",
    "ListCampaigns",
    "ListEvidenceForLead",
    "ListMessages",
    "ListSequenceSteps",
    "MessagePerformanceRow",
    "MessageValidationError",
    "ModelPerformanceRow",
    "NotFoundError",
    "OpportunityUpsertResult",
    "OrganizationContext",
    "OrganizationContextError",
    "PauseCampaign",
    "PipelineStageSummary",
    "PolicyDeniedError",
    "ProcessBounce",
    "ProcessInboundEmail",
    "RecordCrmSyncOutcome",
    "RecordEvidence",
    "RecordReplyClassification",
    "RecordSignal",
    "ResolveOrganizationContext",
    "ResumeCampaign",
    "RevenueAttributionRow",
    "ScoreLead",
    "SelectPersonalizationEvidence",
    "SendMessage",
    "TransitionOpportunityStage",
    "TriggerPerformanceRow",
    "UnsubscribeByToken",
    "Urgency",
    "ValidateCampaign",
    "__version__",
    "can_transition",
    "can_transition_stage",
    "compute_overall_score",
    "determine_conversation_transition",
    "determine_qualification",
    "determine_reason_codes",
    "determine_verification_status",
    "get_brand_voice",
    "rank_signal",
    "summarize_agent_cost",
    "summarize_channel_performance",
    "summarize_funnel",
    "summarize_icp_performance",
    "summarize_message_performance",
    "summarize_model_performance",
    "summarize_pipeline",
    "summarize_revenue_by_source",
    "summarize_trigger_performance",
    "validate_campaign_definition",
]
