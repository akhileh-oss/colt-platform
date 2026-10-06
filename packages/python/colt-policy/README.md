# colt-policy

Authorization and business-safety policy engine.

`evaluate_outbound_send()` (`CLAUDE.md` §17, §17.1, Milestone 16) is the engine CLAUDE.md §17
describes conceptually: a pure function over an `OutboundSendContext` of already-resolved facts,
returning a `PolicyEvaluation` — `ALLOW`/`DENY`/`REQUIRE_APPROVAL`/`DEFER` plus the name of every
failing check, never just the first. This package depends only on `colt_domain`, so it has no
database, clock, or provider access of its own; `colt_application.SendMessage` gathers the
context and is the one use case ever allowed to call `MessageSender.send` once (and only once)
the engine returns `ALLOW`.

```python
from colt_policy import OutboundSendContext, PolicyDecision, evaluate_outbound_send

evaluation = evaluate_outbound_send(
    OutboundSendContext(
        lead_belongs_to_organization=True,
        target_identity_valid=True,
        is_suppressed=False,
        channel_allowed=True,
        campaign_active=True,
        rate_limit_ok=True,
        message_matches_target=True,
        evidence_valid=True,
        no_duplicate_send=True,
        approval_required=True,
        approval_status=ApprovalStatus.APPROVED,
        send_window_ok=True,
    )
)
assert evaluation.decision == PolicyDecision.ALLOW
```

Twelve of §17.1's fifteen mandatory checks are modeled above. Three — contact-permission rules,
provider-credential validity, and compliance checks — have no represented infrastructure yet
(no real channel provider exists before Milestone 17's email subsystem) and are deliberately
left unmodeled; see `colt_policy.outbound`'s own module docstring for why each is deferred
rather than faked with an always-true stub.

See [`docs/architecture/ARCHITECTURE.md` §11](../../../docs/architecture/ARCHITECTURE.md) for the
full mechanism, and `CLAUDE.md` §5 for the layer rules this package must obey.
