"""`ListEvidenceForLead` (CLAUDE.md §12.8, Milestone 15) — the read-only lookup
`PersonalizationAgent` uses to see what it actually has to work with before selecting any of it.

A `Lead` has no evidence of its own (§10.6: evidence attaches to a polymorphic
`entity_type`/`entity_id`, and nothing records evidence against a Lead directly) — it is a
relationship between one `Company` and one `Person`, and that is where the research/discovery
agents' evidence actually lives. This use case resolves both and returns the union, so
`select_evidence` always has a closed, this-lead-relevant set to validate selections against.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.errors import NotFoundError
from colt_application.ports.evidence_repository import EvidenceRepository
from colt_application.ports.lead_repository import LeadRepository
from colt_domain import Evidence


class ListEvidenceForLead:
    def __init__(self, leads: LeadRepository, evidence: EvidenceRepository) -> None:
        self._leads = leads
        self._evidence = evidence

    async def __call__(self, lead_id: UUID) -> list[Evidence]:
        lead = await self._leads.get(lead_id)
        if lead is None:
            raise NotFoundError(f"No lead found with id {lead_id}.")
        company_evidence = await self._evidence.list_by_entity("Company", lead.company_id)
        person_evidence = await self._evidence.list_by_entity("Person", lead.person_id)
        return company_evidence + person_evidence
