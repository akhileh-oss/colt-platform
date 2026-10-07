"""The opportunity pipeline state machine (CLAUDE.md §11.3, Milestone 21).

§11.3 names the pipeline's seven stages as "minimum lifecycle support" but — unlike Lead and
Conversation, whose transition rules CLAUDE.md spells out elsewhere — never states which moves
between them are legal. This milestone's own Build list item ("opportunity state machine") is
the specification, the same documented-design-decision reasoning `campaign_state.py`
(Milestone 14) already applies where CLAUDE.md names a state machine without a transition table:

* `QUALIFIED` -> `DISCOVERY` or `LOST` (a deal can die at any stage; dying at the first stage
  needs no softer label).
* `DISCOVERY` -> `EVALUATION` or `LOST`.
* `EVALUATION` -> `PROPOSAL` or `LOST`.
* `PROPOSAL` -> `NEGOTIATION` or `LOST`.
* `NEGOTIATION` -> `WON` or `LOST` — the only stage that can reach `WON`.
* `WON`/`LOST` — terminal. Neither reopens; a new deal with the same company is a new
  `Opportunity` row, never a resurrected old one.

No stage skips ahead and no stage moves backward — the pipeline is a straight line toward either
terminal outcome, never a cycle.
"""

from __future__ import annotations

from colt_domain import PipelineStage

OPPORTUNITY_TRANSITIONS: dict[PipelineStage, frozenset[PipelineStage]] = {
    PipelineStage.QUALIFIED: frozenset({PipelineStage.DISCOVERY, PipelineStage.LOST}),
    PipelineStage.DISCOVERY: frozenset({PipelineStage.EVALUATION, PipelineStage.LOST}),
    PipelineStage.EVALUATION: frozenset({PipelineStage.PROPOSAL, PipelineStage.LOST}),
    PipelineStage.PROPOSAL: frozenset({PipelineStage.NEGOTIATION, PipelineStage.LOST}),
    PipelineStage.NEGOTIATION: frozenset({PipelineStage.WON, PipelineStage.LOST}),
    PipelineStage.WON: frozenset(),
    PipelineStage.LOST: frozenset(),
}


def can_transition_stage(current: PipelineStage, target: PipelineStage) -> bool:
    return target in OPPORTUNITY_TRANSITIONS[current]
