# ADR-0003 — Typed settings live in a shared `colt-config` package

## Context

`CLAUDE.md` §7 requires typed configuration through `pydantic-settings`, accessed as
`settings.anthropic_api_key` rather than `os.getenv` outside the settings module. §7.3 fixes fifteen
configuration categories. §4 lists the repository's packages, and that list contains no package for
configuration.

Configuration is not needed by the API alone. The Temporal worker (Milestone 06) needs the Temporal
address, the database URL and the feature flags; the AI gateway (Milestone 08) needs the Anthropic
credentials and model routing; database tooling (Milestone 05) needs the connection settings. Every
one of those is a lower layer than the HTTP application.

So the question is not whether settings are typed — §7 settles that — but which package owns them,
and every answer available inside the §4 list is wrong in a way that costs later.

## Decision

We will add one package, `packages/python/colt-config`, exposing a `Settings` aggregate composed of
one `BaseSettings` model per §7.3 category, plus a cached `get_settings()` accessor.

`colt-config` depends on nothing inside Colt. Any package or application may depend on it.

Secrets are typed `SecretStr` so they do not appear in logs, tracebacks or `repr` output, and the
model rejects a configuration that would let local development perform real external side effects
(§6.4).

## Alternatives considered

**Settings in `colt-api`.** The obvious move while Milestone 02 is the only consumer, and wrong by
Milestone 06: `colt-workflows` would have to import the FastAPI application to read the Temporal
address, inverting the dependency direction §5 requires. `CLAUDE.md` §0.1.9 forbids building
something that will obviously need replacing, and this is exactly that.

**Settings in `colt-domain`.** Rejected outright. The domain layer may not know that environment
variables, databases or providers exist (§5.3).

**Settings in `colt-application`.** Closer, since application services are a shared upper layer, but
still wrong: §5.2 defines that package as use cases and application services. Environment
configuration is a bootstrap concern, and burying it there would mean `colt-db` depends on the
application layer to learn its own connection string.

**Settings in `colt-observability`.** Rejected. That package is logging, tracing and metrics
helpers (§4). Configuration is not observability, and the two only look adjacent because both are
cross-cutting.

**No settings package — each consumer reads its own environment variables.** This is what §7
explicitly forbids, and it would scatter `os.getenv` through business code with no single place to
enforce redaction, validation or the §6.4 safety rule.

## Consequences

- The repository has one package more than `CLAUDE.md` §4 lists. That section should be read as
  amended by this ADR.
- Every consumer depends on `colt-config`, which makes it a wide dependency. It is kept deliberately
  small — models and an accessor, no logic — so that width costs little.
- Settings validation runs at construction, so a misconfigured environment fails at startup rather
  than at first use.
- `get_settings()` is cached, so tests that need different configuration must clear the cache. A
  fixture does this.
- If configuration later needs to come from a secrets manager rather than the environment, that
  change is confined to this package.

## Status

Accepted — 2026-08-29
