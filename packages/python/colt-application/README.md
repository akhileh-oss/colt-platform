# colt-application

Use cases and application services coordinating domain objects and ports.

Ports (`colt_application.ports`) are `typing.Protocol`s, not `colt-db` imports — its concrete
repositories satisfy them structurally. `GetLead` is the use case `colt-agents`' `get_lead` tool
calls, realising `CLAUDE.md` §2.3's required path: Typed Tool → Application Service → Repository
→ PostgreSQL.

`colt_application.research.determine_verification_status()` is deterministic source-freshness
logic (CLAUDE.md §19.2, §2.1): it demotes a claim to `STALE` once its source is older than the
freshness threshold, but cannot promote one to `VERIFIED`/`DISPUTED`/`REJECTED` — those require
independent corroboration or human review, mechanisms a later milestone builds. `RecordEvidence`
is the one use case that writes an `Evidence` row (§10.6, §20); it computes
`verification_status` itself rather than trusting a caller-supplied value, since a tool argument
is attacker-adjacent model-decided input. `colt-agents`' `record_evidence` tool is the only
caller.

`colt_application.identity` (CLAUDE.md §22) holds deterministic normalization (`normalize_domain`/
`normalize_email`/`normalize_linkedin_url`/`normalize_name`) and
`DEFAULT_NAME_MATCH_CONFIDENCE_THRESHOLD`. `DiscoverCompany`/`DiscoverPerson` apply §22's exact
layered matching (provider ID, then email/LinkedIn URL, then confidence-gated name) before ever
creating a row — never on fuzzy name similarity. `EnrichCompany`/`EnrichPerson` apply §12.4's
confidence rule: an incoming candidate only overwrites a record's fields when its own
confidence is at least as high as what is already stored. All four take plain scalar
arguments, never a `colt_integrations.enrichment` candidate object directly — this package
depends only on `colt_domain`/`colt_policy`, never on the provider-adapter layer.

`colt_application.signals.rank_signal()` (CLAUDE.md §12.6) is deterministic signal scoring: a
pure function of `signal_type` (weighted by commercial urgency), `confidence`, and freshness
decay (a shorter window than `research`'s, since a "why now" trigger loses relevance faster) —
not a persisted column, reproducible from a `Signal` row's own fields alone. `RecordSignal`
(the one use case `record_signal` calls) is a thinner wrapper than `RecordEvidence`:
`signal_type`/`confidence`/`business_implication` are the model's own judgment, so nothing here
is server-computed beyond persistence itself.

See [`docs/architecture/ARCHITECTURE.md`](../../../docs/architecture/ARCHITECTURE.md) for how this
package fits into the layering, and `CLAUDE.md` §5 for the layer rules it must obey.
