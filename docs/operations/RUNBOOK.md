# Runbook

> Skeleton established in Milestone 00; populated as operable surfaces land (Milestones 01, 17, 18,
> 25). Specification: `CLAUDE.md` §71, §72, §87.

## 1. Local environment

```bash
make install    # dependencies
make check      # lint, typecheck, test, security
make dev        # full local stack — Milestone 01
```

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
