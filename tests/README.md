# Tests

Suites follow `CLAUDE.md` §45. Markers are applied automatically by directory (see `conftest.py`),
so a suite can be selected with `pytest -m <marker>`.

| Directory      | Marker        | Scope                                          | Milestone |
| -------------- | ------------- | ---------------------------------------------- | --------- |
| `unit/`        | _(none)_      | Pure logic, no I/O                             | 02        |
| `integration/` | `integration` | Real Postgres, Redis, Temporal, MinIO          | 05        |
| `e2e/`         | `e2e`         | Drives the running application                 | 03        |
| `workflows/`   | `workflows`   | Temporal workflow test environment             | 06        |
| `security/`    | `security`    | Security and cross-tenant isolation invariants | 04        |
| `evals/`       | `evals`       | AI evaluation suites                           | 23        |

Package-level unit tests live beside their package under `packages/python/*/tests/`.

**Tests never send real outbound messages** (`CLAUDE.md` §29).
