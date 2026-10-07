# Runbook

> Skeleton established in Milestone 00; populated as operable surfaces land (Milestones 01, 17, 18,
> 25, 27). Specification: `CLAUDE.md` §71, §72, §87, §96.

## 1. Local environment

```bash
make install    # dependencies
make dev        # start the local stack and verify it
make health     # re-check service health at any time
make logs       # tail service logs
make down       # stop (volumes preserved)
make check      # lint, typecheck, test, security
```

`make dev` refuses to start if any `FEATURE_REAL_*` flag is enabled in `.env`, so a misconfigured
local environment fails closed rather than reaching a real provider.

To discard local data entirely and start from scratch:

```bash
docker compose down -v && make dev
```

**Service health.** `scripts/dev-health.sh` is the authority, not `docker compose ps`. The OTel
collector image is distroless and the Temporal UI ships no healthcheck, so neither reports a
container health status; the script probes both over HTTP from the host. It also checks that the
`colt-research` bucket exists and that the `colt` Keycloak realm resolves — a service can be up but
unusable.

**Temporal.** The frontend binds to the container IP rather than loopback, so any in-container
probe must target `$(hostname -i):7233`.

Local development performs **no real external side effects**: `FEATURE_REAL_EMAIL`,
`FEATURE_REAL_CRM`, `FEATURE_REAL_CALENDAR` and `FEATURE_REAL_SOCIAL` default to `false`, and email
goes to Mailpit (`CLAUDE.md` §6.4).

## 2. Kill switches

`FEATURE_OUTBOUND_ENABLED` and `FEATURE_AGENTS_ENABLED` halt all outbound sending and all agent
execution respectively. Emergency switches are specified in `CLAUDE.md` §72 and become operable in
Milestone 16.

## 3. Common procedures

_Populated as the relevant milestones land:_

- Pausing a campaign — Milestone 14
- Draining and restarting workers — Milestone 06
- Replaying a failed workflow — Milestone 06
- Investigating a stuck agent run — Milestone 09
- Handling a provider outage — Milestone 20
- Processing an unsubscribe or bounce manually — Milestone 17

## 4. Health checks

_Milestone 02 (API) and Milestone 25 (production)._

## 5. Escalation

_Milestone 29._

## 6. Staging soak test (Milestone 27)

CLAUDE.md §96/§27's full chaos/volume list — thousands of mocked leads, long-running workflows,
provider throttling, duplicate webhooks, worker/API restarts, DB reconnects, Redis failures,
Temporal worker failures, AI provider transient errors — splits across two places:

- **`tests/soak/`** (`make test-soak`) runs for real against local Postgres/Redis at a few-
  hundred-row, single-machine scale, as a routine regression suite: identity-resolution
  concurrency (duplicate-creation races), a real Postgres restart, a real Redis restart,
  duplicate-webhook-delivery idempotency, and volume + tenant isolation. **Found and fixed two
  real bugs this way** — `DiscoverCompany`/`DiscoverPerson` could create duplicate `Company`/
  `Person` rows under concurrent discovery (fixed with partial unique indexes +
  `colt_domain.DuplicateIdentityError`), and a duplicate unsubscribe webhook delivery raised a
  raw, unhandled `IntegrityError` instead of the clean 204 its own docstring promised (fixed by
  making `SqlAlchemySuppressionRepository.add()` idempotent under a `SAVEPOINT`).
- **The literal "thousands... in staging" run** is `tests/soak/load/locustfile.py`
  (`uv run locust -f tests/soak/load/locustfile.py --host <staging-url> --users 50
--spawn-rate 5 --run-time 30m --headless`), against a real Milestone 25 staging environment.
  **Not run in this sandbox** — no real AWS account exists here to have applied Milestone 25's
  Terraform against, so there is no staging URL to point this at. Before running it for real:
  1. Confirm staging is up: `curl <staging-url>/api/v1/meta` and `curl <staging-url>/`.
  2. Seed realistic volume (thousands of companies/people/leads) — reuse `apps/api/scripts/
seed_dev_data.py`'s own pattern, scaled up, or drive `DiscoverCompany`/`DiscoverPerson`
     directly against staging's database from a one-off script.
  3. Run the load test for the sustained duration CLAUDE.md's "realistic workloads" calls for
     (30+ minutes, not a smoke-test-length run).
  4. During the run, inject each remaining chaos scenario by hand against the real ECS
     services: stop/start an `api`/`worker` task (API/worker restart), scale a service down to
     0 and back (Temporal worker failure), temporarily revoke the Anthropic API key in Secrets
     Manager and restore it (AI provider transient error).
  5. Verify the acceptance criterion directly against the database afterward: no duplicate
     rows, no cross-tenant rows visible from the wrong organization's own RLS-scoped query, no
     workflow stuck in a non-terminal state with no further progress possible.
