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
testable in CI (`CLAUDE.md` §102). Enforced by `.github/workflows/ci.yml` (Milestone 26): every
push and PR runs install/lint/typecheck/unit/integration/e2e/security-scan/migration-validation
from a fresh checkout, with no step assuming a prior local `make` run.

## 5. Rollback

Deploys are image-tag-driven, not a separate rollback mechanism: `terraform apply` (`deploy-
staging`/`deploy-production` in `.github/workflows/`) always sets `api_image`/`web_image`/
`worker_image` explicitly, so rolling back is redeploying the previous known-good tag through the
same pipeline — never editing running infrastructure by hand.

- **Staging**: re-run `.github/workflows/ci.yml`'s `deploy-staging` job for the prior commit's
  SHA (re-run that workflow run, or push a revert commit — either produces the same
  `api_image=...:<prior-sha>` Terraform variables).
- **Production**: trigger `deploy-production.yml` manually (`workflow_dispatch`) with
  `image_tag` set to the last known-good tag — the same explicit-approval path a forward
  deployment uses, never bypassed for a rollback.
- Database migrations are the one part this cannot automatically undo: `CLAUDE.md` §90's
  backward-compatible-during-transition rule is what makes "redeploy an older image against
  the newer schema" safe in the meantime; a destructive migration's own `downgrade()` is a
  deliberate, separate decision, never run automatically as part of an application rollback.
