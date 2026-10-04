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

See [`docs/api/README.md`](../../docs/api/README.md) for the API contract, and
[`docs/architecture/ARCHITECTURE.md`](../../docs/architecture/ARCHITECTURE.md) for the request
path.
