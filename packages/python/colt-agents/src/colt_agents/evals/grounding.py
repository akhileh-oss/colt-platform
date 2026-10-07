"""Evidence-grounding checks (CLAUDE.md §45.5's "evidence correctness"/"hallucination rate",
Milestone 23).

Deliberately generic: a caller hands over the set of evidence (or any other reference) IDs an
agent's output actually cited, and the set that was actually recorded during that same run
(e.g. every `Evidence.id` a `record_evidence` tool call really produced) — never a specific
agent's output schema, so this works for `ResearchAgent`'s `DossierClaim.evidence_ids` today and
any future agent that cites stored evidence tomorrow without this module changing.

A cited ID absent from the recorded set is not "missing evidence" (`DossierClaim`'s own
pydantic validator already makes an evidence-less `FACT` claim structurally impossible) — it is
a *fabricated* citation: a real-looking `UUID` the model produced but that was never backed by
an actual `record_evidence` call. That is exactly what "hallucination rate" means for a
citation-producing agent, and exactly what CLAUDE.md §2.6 ("evidence before assertions") rules
out.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GroundingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    grounded: bool
    hallucinated_ids: frozenset[UUID]


def check_evidence_grounding(*, cited_ids: set[UUID], recorded_ids: set[UUID]) -> GroundingResult:
    hallucinated = cited_ids - recorded_ids
    return GroundingResult(grounded=not hallucinated, hallucinated_ids=frozenset(hallucinated))
