# Architecture

> Skeleton established in Milestone 00. Sections are filled in as the milestones that build each
> layer land. `CLAUDE.md` remains the authoritative specification — this document explains **how
> the code actually realises it**, and must be updated whenever behaviour changes (`CLAUDE.md` §63).

## 1. System shape

Colt is a deterministic platform with AI reasoning components. Responsibilities are separated
absolutely (`CLAUDE.md` §2.1):

| Concern                              | Owner                         |
| ------------------------------------ | ----------------------------- |
| Reasoning                            | Claude, via the agent runtime |
| Controlled capabilities              | Typed tool registry           |
| Authorization and business safety    | Policy engine                 |
| Deterministic business logic         | Application services          |
| Business source of truth             | PostgreSQL                    |
| Durable orchestration                | Temporal                      |
| Cache, locks, ephemeral coordination | Redis                         |
| API boundary                         | FastAPI                       |
| Presentation                         | Next.js                       |

## 2. Layering

Dependencies point inward:

```text
Presentation → API/UI → Application → Domain → Ports → Infrastructure
```

The domain layer imports no framework, ORM, SDK or provider module (`CLAUDE.md` §5.3).

Two mechanisms carry this, and it is worth being precise about what each does. The workspace
dependency graph in each `pyproject.toml` **declares** the shape — it is the documentation of
intent — but it does not enforce it: `uv` installs every workspace package into a single shared
virtualenv, so at runtime any package can import anything present. Enforcement therefore comes
from `packages/python/colt-domain/ruff.toml`, which bans the forbidden modules outright via
`flake8-tidy-imports`. A forbidden import in the domain fails `make lint`, whether or not it is
used.

## 3. Package map

| Package              | Layer          | Responsibility                                           |
| -------------------- | -------------- | -------------------------------------------------------- |
| `colt-domain`        | Domain         | Entities, value objects, invariants, deterministic rules |
| `colt-application`   | Application    | Use cases, orchestration of domain objects and ports     |
| `colt-policy`        | Application    | Authorization and business-safety decisions              |
| `colt-db`            | Infrastructure | SQLAlchemy models, repositories, migrations              |
| `colt-integrations`  | Infrastructure | Provider adapters behind domain-facing ports             |
| `colt-ai`            | Infrastructure | AI gateway: model routing, usage and cost accounting     |
| `colt-agents`        | Application    | Agent definitions, prompts, runtime integration          |
| `colt-workflows`     | Application    | Temporal workflows and activities                        |
| `colt-observability` | Cross-cutting  | Logging, tracing, metrics                                |
| `colt-api`           | Presentation   | FastAPI routers, DTOs, composition root                  |

## 4. Request path

_To be documented in Milestone 02._

## 5. Data flow: the core product loop

_To be documented as Milestones 10–22 land. The loop is specified in `CLAUDE.md` §1.3._

## 6. Deployment topology

_To be documented in Milestone 25._
