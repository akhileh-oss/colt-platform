"""Agent definitions, the typed tool interface, and the agent runtime (CLAUDE.md §12, §68)."""

from colt_agents.definition import AgentDefinition
from colt_agents.discovery_agent import AGENT_NAME as DISCOVERY_AGENT_NAME
from colt_agents.discovery_agent import AGENT_VERSION as DISCOVERY_AGENT_VERSION
from colt_agents.discovery_agent import (
    DISCOVERY_AGENT_DEFINITION,
    DiscoveredCompany,
    DiscoveredPerson,
    DiscoveryAgentInput,
    DiscoveryAgentOutput,
)
from colt_agents.enrichment_agent import AGENT_NAME as ENRICHMENT_AGENT_NAME
from colt_agents.enrichment_agent import AGENT_VERSION as ENRICHMENT_AGENT_VERSION
from colt_agents.enrichment_agent import (
    ENRICHMENT_AGENT_DEFINITION,
    EnrichedCompanySummary,
    EnrichedPersonSummary,
    EnrichmentAgentInput,
    EnrichmentAgentOutput,
)
from colt_agents.errors import (
    AgentError,
    AgentOutputValidationError,
    AgentTimeoutError,
    MaxToolCallsExceededError,
    PromptNotFoundError,
    ToolNotPermittedError,
    ToolNotRegisteredError,
)
from colt_agents.example_agent import (
    AGENT_NAME,
    AGENT_VERSION,
    EXAMPLE_AGENT_DEFINITION,
    ExampleAgentInput,
    ExampleAgentOutput,
)
from colt_agents.ports import AgentRunRepository, ToolCallRepository
from colt_agents.prompts import load_prompt
from colt_agents.registry import ToolRegistry
from colt_agents.research_agent import AGENT_NAME as RESEARCH_AGENT_NAME
from colt_agents.research_agent import AGENT_VERSION as RESEARCH_AGENT_VERSION
from colt_agents.research_agent import (
    RESEARCH_AGENT_DEFINITION,
    ClaimType,
    DossierClaim,
    ResearchAgentInput,
    ResearchDossier,
)
from colt_agents.runtime import AgentRuntime
from colt_agents.signal_agent import AGENT_NAME as SIGNAL_AGENT_NAME
from colt_agents.signal_agent import AGENT_VERSION as SIGNAL_AGENT_VERSION
from colt_agents.signal_agent import (
    SIGNAL_AGENT_DEFINITION,
    SignalAgentInput,
    SignalAgentOutput,
)
from colt_agents.tool import Tool

__version__ = "0.1.0"

__all__ = [
    "AGENT_NAME",
    "AGENT_VERSION",
    "DISCOVERY_AGENT_DEFINITION",
    "DISCOVERY_AGENT_NAME",
    "DISCOVERY_AGENT_VERSION",
    "ENRICHMENT_AGENT_DEFINITION",
    "ENRICHMENT_AGENT_NAME",
    "ENRICHMENT_AGENT_VERSION",
    "EXAMPLE_AGENT_DEFINITION",
    "RESEARCH_AGENT_DEFINITION",
    "RESEARCH_AGENT_NAME",
    "RESEARCH_AGENT_VERSION",
    "SIGNAL_AGENT_DEFINITION",
    "SIGNAL_AGENT_NAME",
    "SIGNAL_AGENT_VERSION",
    "AgentDefinition",
    "AgentError",
    "AgentOutputValidationError",
    "AgentRunRepository",
    "AgentRuntime",
    "AgentTimeoutError",
    "ClaimType",
    "DiscoveredCompany",
    "DiscoveredPerson",
    "DiscoveryAgentInput",
    "DiscoveryAgentOutput",
    "DossierClaim",
    "EnrichedCompanySummary",
    "EnrichedPersonSummary",
    "EnrichmentAgentInput",
    "EnrichmentAgentOutput",
    "ExampleAgentInput",
    "ExampleAgentOutput",
    "MaxToolCallsExceededError",
    "PromptNotFoundError",
    "ResearchAgentInput",
    "ResearchDossier",
    "SignalAgentInput",
    "SignalAgentOutput",
    "Tool",
    "ToolCallRepository",
    "ToolNotPermittedError",
    "ToolNotRegisteredError",
    "ToolRegistry",
    "__version__",
    "load_prompt",
]
