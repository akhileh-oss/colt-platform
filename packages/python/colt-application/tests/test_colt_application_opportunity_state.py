"""The opportunity pipeline state machine (CLAUDE.md §11.3, Milestone 21)."""

from __future__ import annotations

import pytest

from colt_application.opportunity_state import can_transition_stage
from colt_domain import PipelineStage


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (PipelineStage.QUALIFIED, PipelineStage.DISCOVERY, True),
        (PipelineStage.QUALIFIED, PipelineStage.LOST, True),
        (PipelineStage.QUALIFIED, PipelineStage.EVALUATION, False),
        (PipelineStage.QUALIFIED, PipelineStage.WON, False),
        (PipelineStage.DISCOVERY, PipelineStage.EVALUATION, True),
        (PipelineStage.DISCOVERY, PipelineStage.LOST, True),
        (PipelineStage.DISCOVERY, PipelineStage.QUALIFIED, False),
        (PipelineStage.EVALUATION, PipelineStage.PROPOSAL, True),
        (PipelineStage.EVALUATION, PipelineStage.LOST, True),
        (PipelineStage.PROPOSAL, PipelineStage.NEGOTIATION, True),
        (PipelineStage.PROPOSAL, PipelineStage.LOST, True),
        (PipelineStage.NEGOTIATION, PipelineStage.WON, True),
        (PipelineStage.NEGOTIATION, PipelineStage.LOST, True),
        (PipelineStage.NEGOTIATION, PipelineStage.DISCOVERY, False),
        (PipelineStage.WON, PipelineStage.LOST, False),
        (PipelineStage.WON, PipelineStage.NEGOTIATION, False),
        (PipelineStage.LOST, PipelineStage.WON, False),
        (PipelineStage.LOST, PipelineStage.QUALIFIED, False),
    ],
)
def test_can_transition_stage_matches_the_documented_pipeline(
    current: PipelineStage, target: PipelineStage, expected: bool
) -> None:
    assert can_transition_stage(current, target) is expected


def test_won_and_lost_are_both_terminal() -> None:
    for target in PipelineStage:
        assert can_transition_stage(PipelineStage.WON, target) is False
        assert can_transition_stage(PipelineStage.LOST, target) is False
