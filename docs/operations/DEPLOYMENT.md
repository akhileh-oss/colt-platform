# Deployment

> Skeleton established in Milestone 00; populated in Milestones 25–26 and exercised in 27–30.
> Specification: `CLAUDE.md` §52, §56, §103.

## 1. Environments

`local`, `test`, `staging`, `production` — each with separate credentials and infrastructure. No
local configuration may target production (`CLAUDE.md` §7.1, §6.4).

## 2. Deployment order

```text
1. infrastructure
2. database compatibility migration
3. backend
4. worker
5. frontend
6. smoke tests
7. feature flags
8. controlled activation
```

Destructive side effects stay disabled until smoke tests pass (`CLAUDE.md` §103).

## 3. Migration safety

Migrations are reversible where practical, safe for rolling deployment, and backward compatible
during transition. Production schema is never modified by hand (`CLAUDE.md` §9.8, §90).

## 4. Clean build

A clean build is reproducible from a fresh checkout with no generated files assumed present, and is
testable in CI (`CLAUDE.md` §102). CI enforcement lands in Milestone 26.

## 5. Rollback

_Milestone 26._
