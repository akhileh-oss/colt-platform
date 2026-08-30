# Architecture Decision Records

An ADR is **required** before changing: database type, ORM, workflow engine, authentication,
frontend framework, API architecture, model-provider architecture, tool architecture, tenancy
model, data-storage architecture, deployment topology, or the security model (`CLAUDE.md` §64).

Deviating from `CLAUDE.md` without an ADR is not permitted (`CLAUDE.md` §0.1).

## Process

1. Copy [`ADR-TEMPLATE.md`](./ADR-TEMPLATE.md) to `ADR-<next number>-<slug>.md`.
2. Write it while the decision is still open — an ADR is a proposal, not a postscript.
3. Set **Status** to `Proposed`, then `Accepted`, `Rejected` or `Superseded by ADR-NNN`.
4. Never edit an accepted ADR's decision. Supersede it with a new one.

## Index

| ADR                                                  | Decision                                                            | Status   |
| ---------------------------------------------------- | ------------------------------------------------------------------- | -------- |
| [0001](./ADR-0001-adopt-the-colt-reference-stack.md) | Adopt the Colt reference stack                                      | Accepted |
| [0002](./ADR-0002-separate-platform-repository.md)   | Build the platform in a repository separate from the marketing site | Accepted |
| [0003](./ADR-0003-shared-settings-package.md)        | Typed settings live in a shared `colt-config` package               | Accepted |
| [0004](./ADR-0004-typed-api-client-generation.md)    | TypeScript client generated with openapi-typescript + openapi-fetch | Accepted |
