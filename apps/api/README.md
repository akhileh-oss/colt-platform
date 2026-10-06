# colt-api

The FastAPI application: routers, request/response DTOs, middleware, and the composition root
that wires application services to their infrastructure adapters.

This package holds no business logic — see `CLAUDE.md` §5.1.

```bash
make dev     # infrastructure
make api     # this application, with reload, on http://localhost:8000
```

| Module            | Responsibility                                                        |
| ----------------- | --------------------------------------------------------------------- |
| `app.py`          | Application factory. Wires settings, logging, middleware and routers. |
| `middleware.py`   | Request identity, access logging, security headers, body size limit.  |
| `errors.py`       | The §36 error taxonomy and the §25.4 response envelope.               |
| `readiness.py`    | Registry of dependencies that `/ready` verifies.                      |
| `dependencies.py` | Dependency-injection conventions.                                     |
| `routers/`        | `health` (probes) and `v1` (versioned product routes).                |

`routers/v1/campaigns.py` (Milestone 14) is the first real DB-backed CRUD resource: `POST`/
`GET /campaigns`, `GET /campaigns/{id}`, and the `validate`/`pause`/`resume` lifecycle actions,
each driving a `colt_application` use case through a `SqlAlchemyCampaignRepository` bound to
the caller's own `organization_id`. `CAMPAIGN_WRITE` gates creating a campaign; `CAMPAIGN_LAUNCH`
gates the three state-changing actions — a deliberate split from `CAMPAIGN_READ`
(`colt_domain.roles.DEFAULT_ROLE_PERMISSIONS`). `errors.py`'s taxonomy gained `ConflictError`
(409) for an `InvalidCampaignTransitionError`; `CampaignValidationError` maps to the existing
`ValidationError` (422), carrying every failing rule in `details.issues`. The same module also
nests `POST`/`GET /campaigns/{id}/sequence-steps` — `CAMPAIGN_WRITE`-gated to add, `CAMPAIGN_
READ`-gated to list — closing a gap Milestone 14's own Build list named but this PR initially
missed: a `SequenceStep` entity (CLAUDE.md §10.10), not just Campaign's flat `channels` list.

`GET /campaigns/{id}/messages` (Milestone 15) lists a campaign's drafted `Message` rows,
gated by `MESSAGE_APPROVE` — reused rather than paired with a new read-only permission, since
every role that can review a message already carries it. It is the first route whose rows are
only ever written by an agent pipeline (`PersonalizationAgent` → `MessagingAgent`) rather than
by another HTTP request; the route itself still only calls `colt_application.ListMessages`.

`POST /campaigns/{id}/messages/{message_id}/approve` and `/reject` (Milestone 16) finally make
the message-review UI's buttons real, both gated by `MESSAGE_APPROVE`. Both verify the message
actually belongs to the campaign named in the URL before deciding it — the nested route accepts
`campaign_id` for REST shape, but nothing upstream of this check enforced that it matches the
message's own `campaign_id`. `InvalidApprovalTransitionError` (an already-decided approval)
maps to the existing `ConflictError` (409), the same taxonomy slot `InvalidCampaignTransitionError`
uses.

`routers/v1/unsubscribe.py` (`POST /unsubscribe/{organization_id}/{message_id}`, CLAUDE.md
§18.2, §29, Milestone 17) is the API's first deliberately unauthenticated route: it is the
target of the `List-Unsubscribe`/`List-Unsubscribe-Post` headers `SmtpEmailProvider` sets (RFC
8058), which a mail client — not a signed-in user — calls. `organization_id` is routing
information carried in the link, not a credential: Row-Level Security requires a tenant bound
before any lookup can run at all, and a bare `message_id` has no organization to bind. It
responds `204` whether or not the token resolves, the standard unsubscribe-link convention
(never confirm or deny a specific id to an unauthenticated caller, and never let a mail client's
one-click retry start erroring once the first attempt already succeeded).

See [`docs/api/README.md`](../../docs/api/README.md) for the API contract, and
[`docs/architecture/ARCHITECTURE.md`](../../docs/architecture/ARCHITECTURE.md) for the request
path.
