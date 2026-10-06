"""The outbound-send policy engine (CLAUDE.md §17, §17.1) — "Every external side effect must
pass the Colt policy engine." `colt_policy` depends only on `colt_domain` (§5.2's layering: this
package sits below `colt_application`, so it must stay free of any port, repository or I/O), so
`evaluate_outbound_send()` is a pure function over already-resolved facts — it does not reach
into a database, a clock, or a provider itself. The application layer's `SendMessage` use case
is responsible for gathering `OutboundSendContext` from its own ports and then calling here.

§17.1 lists fifteen mandatory checks. Twelve are modeled below, each as one boolean or optional
field on `OutboundSendContext`. The remaining three have no represented infrastructure yet in
this codebase and are deliberately deferred rather than faked:

- check 5, "contact permission rules pass" — CLAUDE.md defines no contact-permission model
  beyond consent already captured by suppression (check 4) and email validity (part of check 3);
- check 13, "provider credential is valid" — no real channel provider exists yet (`CLAUDE.md`
  §29's email subsystem is Milestone 17's job);
- check 15, "compliance checks pass" — CLAUDE.md names no specific compliance ruleset to check.

Each deferred check will get a real field here in the milestone that builds the infrastructure
it needs, rather than being represented today by an always-true stub that would quietly assert
nothing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from colt_domain import ApprovalStatus


class PolicyDecision(StrEnum):
    """CLAUDE.md §17's four possible policy outcomes."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DEFER = "DEFER"


class OutboundSendContext(BaseModel):
    """Already-resolved facts an outbound send must be checked against — every field here is
    something the caller looked up itself; this model asserts nothing about how."""

    model_config = ConfigDict(frozen=True)

    lead_belongs_to_organization: bool
    target_identity_valid: bool
    is_suppressed: bool
    channel_allowed: bool
    campaign_active: bool
    rate_limit_ok: bool
    message_matches_target: bool
    evidence_valid: bool
    no_duplicate_send: bool
    approval_required: bool
    approval_status: ApprovalStatus
    send_window_ok: bool


class PolicyEvaluation(BaseModel):
    """The engine's verdict: a decision plus the name of every failing check, so a caller (and
    a test) can see exactly why a send was not allowed, not just that it wasn't."""

    model_config = ConfigDict(frozen=True)

    decision: PolicyDecision
    failed_checks: tuple[str, ...] = ()


#: §17.1 checks 1-3 and 6-11, 14 — every boolean check that, if false, blocks the send outright
#: rather than merely requiring a human decision. Order follows §17.1's own numbering.
_DENY_IF_FALSE: tuple[tuple[str, str], ...] = (
    ("lead_belongs_to_organization", "lead_belongs_to_organization"),
    ("target_identity_valid", "target_identity_valid"),
    ("channel_allowed", "channel_allowed"),
    ("campaign_active", "campaign_active"),
    ("rate_limit_ok", "rate_limit_ok"),
    ("message_matches_target", "message_matches_target"),
    ("evidence_valid", "evidence_valid"),
    ("no_duplicate_send", "no_duplicate_send"),
    ("send_window_ok", "send_window_ok"),
)


def evaluate_outbound_send(context: OutboundSendContext) -> PolicyEvaluation:
    """§17.1's mandatory outbound checks, evaluated deterministically. "Failure of any mandatory
    check must block the send" — every boolean check is evaluated regardless of earlier
    failures, so a caller sees every reason, not just the first.
    """
    failed = [name for attribute, name in _DENY_IF_FALSE if not getattr(context, attribute)]

    # Suppression (§18.1: "No campaign or agent may override a suppression entry") is checked
    # on its own, separate from the DENY_IF_FALSE checks above, because it is the one check
    # CLAUDE.md singles out as absolute — it is never merely one of several equally-weighted
    # boolean gates.
    if context.is_suppressed:
        failed.append("is_suppressed")

    if failed:
        return PolicyEvaluation(decision=PolicyDecision.DENY, failed_checks=tuple(failed))

    if context.approval_required and context.approval_status != ApprovalStatus.APPROVED:
        return PolicyEvaluation(
            decision=PolicyDecision.REQUIRE_APPROVAL, failed_checks=("approval_status",)
        )

    return PolicyEvaluation(decision=PolicyDecision.ALLOW)
