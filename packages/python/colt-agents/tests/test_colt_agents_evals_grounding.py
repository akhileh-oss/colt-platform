"""`colt_agents.evals.grounding` (CLAUDE.md §2.6, §45.5, §68, Milestone 23)."""

from __future__ import annotations

from uuid import uuid4

from colt_agents.evals.grounding import check_evidence_grounding


def test_grounded_when_every_cited_id_was_actually_recorded() -> None:
    recorded = uuid4()

    result = check_evidence_grounding(cited_ids={recorded}, recorded_ids={recorded, uuid4()})

    assert result.grounded is True
    assert result.hallucinated_ids == frozenset()


def test_not_grounded_when_a_cited_id_was_never_recorded() -> None:
    recorded = uuid4()
    hallucinated = uuid4()

    result = check_evidence_grounding(cited_ids={recorded, hallucinated}, recorded_ids={recorded})

    assert result.grounded is False
    assert result.hallucinated_ids == frozenset({hallucinated})


def test_citing_nothing_is_trivially_grounded() -> None:
    result = check_evidence_grounding(cited_ids=set(), recorded_ids={uuid4()})

    assert result.grounded is True
