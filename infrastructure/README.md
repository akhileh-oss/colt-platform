# Infrastructure

```text
docker/
  postgres/init/  SQL run once on first database initialisation (pgvector, pgcrypto)
  keycloak/       Realm import for the local `colt` realm
  otel/           OpenTelemetry Collector configuration
  worker/         Dockerfile for the Temporal worker (`colt_workflows`, Milestone 26) — no
                  `apps/` directory of its own, so it lives alongside other infra config
terraform/
  bootstrap/      One-time: the S3 state bucket + DynamoDB lock table every environment's
                  own state lives in. Applied once by hand, outside any environment's backend.
  modules/        Leaf modules: networking, database, cache, object_storage, secrets, compute,
                  temporal, dns_tls, observability, alerting, backups — one AWS concern each.
  environment/    Composes every leaf module into one environment. Called by, not called
                  instead of, each environment's own root config below.
environments/
  local/          Reserved; the local stack is defined by ../docker-compose.yml
  staging/        Staging — its own Terraform root, own backend, own tfvars
  production/     Production — same shape as staging, HA knobs turned on
  oracle-free/    $0/month alternative to staging/production, on OCI instead of AWS — see
                  docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md. Not a CLAUDE.md milestone.
terraform/oracle/
  modules/        Leaf modules for the OCI alternative: network, compute — far fewer than AWS's
                  because one instance has no NAT/ALB/multi-AZ to configure.
```

The local stack is declared in `docker-compose.yml` at the repository root and started with
`make dev`. `apps/api/Dockerfile`, `apps/web/Dockerfile`, and `docker/worker/Dockerfile`
(Milestone 26) build the three production images `.github/workflows/ci.yml` pushes to ECR and
`terraform/modules/compute` runs — the application code they package was added across
Milestones 02, 03, and 06, but local development itself still runs it directly (`make api`/
`make web`/`make worker`), never through these images.

Environments have separate credentials and separate infrastructure. Local configuration must never
be able to target production (`CLAUDE.md` §7.1, §6.4). `staging/` and `production/` are
deliberately separate Terraform roots — separate state files, separate `backend.tf` keys, separate
provider configuration each — so a mistaken `terraform apply` run from one directory can never
reach the other's resources (`CLAUDE.md` §53's "separate state/configuration for staging and
production").

No secret is stored here. Production secrets come from a managed secrets service (`CLAUDE.md`
§7.2) — `terraform/modules/secrets` creates each secret's container and IAM access, never its
real value, which an operator sets by hand after `apply`. See `docs/architecture/ARCHITECTURE.md`
§20 for the full Milestone 25 design (why self-hosted Temporal, why ECS Fargate, what remains
`NOT RUN` in this environment and why).

**Bringing up a new environment for the first time:**

```bash
# once per AWS account, never per environment:
cd terraform/bootstrap && terraform init && terraform apply

cd ../../environments/staging   # or production
terraform init
terraform plan   # review before applying against real infrastructure
terraform apply
# then, by hand, once: replace every secret's "REPLACE_ME_AFTER_APPLY" placeholder
# (terraform/modules/secrets) with its real value via the AWS console or
# `aws secretsmanager put-secret-value`.
```

**CI/CD setup (Milestone 26, one-time, by a repo admin):** `.github/workflows/ci.yml` and
`deploy-production.yml` need these repository secrets — `AWS_CI_ROLE_ARN` (assumed by `ci.yml`
to push images and apply staging; least-privilege, scoped to ECR push + the staging Terraform
state/resources), `AWS_CD_ROLE_ARN` (assumed by `deploy-production.yml`; scoped to production's
own state/resources, deliberately a separate role from staging's), and `ECR_REGISTRY` (the
account's ECR registry hostname). None of these is a long-lived AWS access key — both roles are
assumed via GitHub's OIDC provider (`aws-actions/configure-aws-credentials`), which itself needs
an IAM OIDC identity provider for `token.actions.githubusercontent.com` configured once per AWS
account (outside this repository's own Terraform, since it is an IAM-account-wide resource, not
scoped to one environment). Production additionally needs a **required reviewer** configured on
this repository's "production" GitHub Environment (Settings → Environments → production) —
`CLAUDE.md` §56's "production deployment must require an explicit release step/approval" is
only actually enforced once that reviewer is set; `deploy-production.yml` declares the
dependency on it but cannot configure it from a workflow file.
