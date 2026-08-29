# Infrastructure

```text
docker/         Dockerfiles and Compose service definitions   (Milestone 01, 25)
terraform/      Cloud infrastructure as code                  (Milestone 25)
environments/   Per-environment configuration                 (Milestone 01, 25)
  local/        Docker Compose local stack
  staging/      Staging configuration
  production/   Production configuration
```

Environments have separate credentials and separate infrastructure. Local configuration must never
be able to target production (`CLAUDE.md` §7.1, §6.4).

No secret is stored here. Production secrets come from a managed secrets service (`CLAUDE.md` §7.2).
