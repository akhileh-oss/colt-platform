"""Brand voice configuration (CLAUDE.md §68 Milestone 15's "brand voice config" Build item).

CLAUDE.md defines no schema for this — unlike `icp_definition`/`rules`/`schedule`/`limits`,
Campaign's own §10.9 fields, brand voice has no named home anywhere in the spec. `Organization.
settings` (§10.1) is already the tenant-wide free-form config bag every other unspecified,
per-tenant setting would belong in, so this is a documented design decision to use it — a
`settings["brand_voice"]` sub-key — rather than a new column or table for one more config blob.

`MessagingAgent` receives the resolved value as a plain field on its own input (the same
"already-known fact" pattern `ScoringAgentInput`'s `icp_fit`/`signal_strength`/`timing` and
`ResearchAgentInput`'s `company_name`/`company_domain` already use) rather than fetching it
itself — tone is a prompt-level instruction, not something a tool call could validate
deterministically the way `select_evidence` validates evidence_ids.
"""

from __future__ import annotations

from typing import Any

from colt_domain import Organization

#: Deliberately generic and safe-by-default: every organization gets a sane voice even before
#: anyone configures one.
DEFAULT_BRAND_VOICE: dict[str, Any] = {
    "tone": "Professional, concise, and specific. No hype, no fake urgency.",
    "avoid": ["spammy superlatives", "excessive exclamation points", "generic flattery"],
}


def get_brand_voice(organization: Organization) -> dict[str, Any]:
    """This organization's configured brand voice, or `DEFAULT_BRAND_VOICE` if none is set."""
    value = organization.settings.get("brand_voice")
    return value if isinstance(value, dict) else DEFAULT_BRAND_VOICE
