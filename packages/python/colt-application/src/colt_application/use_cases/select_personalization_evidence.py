"""`SelectPersonalizationEvidence` (CLAUDE.md §12.8, Milestone 15) — the one validating step
between "the model names some evidence_ids" and "those evidence_ids are trustworthy."

Mirrors `RecordEvidence`'s reasoning: a tool argument is attacker-adjacent, model-decided input,
so this use case re-checks every claimed `evidence_id` against this organization's real
`Evidence` rows rather than trusting the model's own assertion that they exist and are relevant.
This is what makes CLAUDE.md §12.8's "no unsupported claims" and "preserve evidence IDs" rules
structurally checked, not merely prompted for — the same role `DossierClaim`'s FACT validator
(Milestone 10) plays for research claims.
"""

from __future__ import annotations

from uuid import UUID

from colt_application.errors import MessageValidationError
from colt_application.ports.evidence_repository import EvidenceRepository
from colt_domain import Evidence


class SelectPersonalizationEvidence:
    def __init__(self, evidence: EvidenceRepository) -> None:
        self._evidence = evidence

    async def __call__(self, evidence_ids: list[UUID]) -> list[Evidence]:
        if not evidence_ids:
            raise MessageValidationError(
                ["evidence_ids must not be empty — personalization must be evidence-based."]
            )
        resolved: list[Evidence] = []
        missing: list[str] = []
        for evidence_id in evidence_ids:
            found = await self._evidence.get(evidence_id)
            if found is None:
                missing.append(str(evidence_id))
            else:
                resolved.append(found)
        if missing:
            raise MessageValidationError(
                [f"evidence_id {value} does not exist in this organization." for value in missing]
            )
        return resolved
