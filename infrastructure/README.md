# Infrastructure

```text
docker/
  postgres/init/  SQL run once on first database initialisation (pgvector, pgcrypto)
  keycloak/       Realm import for the local `colt` realm
  otel/           OpenTelemetry Collector configuration
terraform/        Cloud infrastructure as code                  (Milestone 25)
environments/     Per-environment configuration                 (Milestone 25)
  local/          Reserved; the local stack is defined by ../docker-compose.yml
  staging/        Staging configuration
  production/     Production configuration
```

The local stack is declared in `docker-compose.yml` at the repository root and started with
`make dev`. Application images (api, web, worker) are added in Milestones 02, 03 and 06.

Environments have separate credentials and separate infrastructure. Local configuration must never
be able to target production (`CLAUDE.md` §7.1, §6.4).

No secret is stored here. Production secrets come from a managed secrets service (`CLAUDE.md` §7.2).
