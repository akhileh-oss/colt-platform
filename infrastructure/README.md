# Infrastructure

```text
docker/
  postgres/init/  SQL run once on first database initialisation (pgvector, pgcrypto)
  keycloak/       Realm import for the local `colt` realm
  otel/           OpenTelemetry Collector configuration
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
```

The local stack is declared in `docker-compose.yml` at the repository root and started with
`make dev`. Application images (api, web, worker) are added in Milestones 02, 03 and 06.

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
