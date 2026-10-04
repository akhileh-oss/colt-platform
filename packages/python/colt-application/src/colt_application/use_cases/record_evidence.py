"""Record one sourced, dated claim as `Evidence` (CLAUDE.md §2.3, §2.6, §20).

The use case `colt-agents`' `record_evidence` tool calls — never `colt-db` directly. Computes
`verification_status` itself (`colt_application.research.determine_verification_status`) rather
than trusting a caller-supplied value: a tool argument is attacker-adjacent input (it came from
whatever the model decided to pass), and verification state is exactly the kind of fact §2.1
reserves for deterministic application logic, not model judgment.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from colt_application.ports.evidence_repository import EvidenceRepository
from colt_application.research import determine_verification_status
from colt_domain import Evidence


class RecordEvidence:
    def __init__(self, evidence: EvidenceRepository) -> None:
        self._evidence = evidence

    async def __call__(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        claim: str,
        source_url: str,
        observed_at: datetime,
        source_type: str | None = None,
        source_date: date | None = None,
        excerpt: str | None = None,
        confidence: float | None = None,
    ) -> Evidence:
        verification_status = determine_verification_status(
            source_date=source_date, observed_at=observed_at, now=datetime.now(UTC)
        )
        return await self._evidence.add(
            entity_type=entity_type,
            entity_id=entity_id,
            claim=claim,
            source_url=source_url,
            observed_at=observed_at,
            source_type=source_type,
            source_date=source_date,
            excerpt=excerpt,
            confidence=confidence,
            verification_status=verification_status,
        )
