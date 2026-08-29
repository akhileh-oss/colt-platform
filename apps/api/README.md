# colt-api

The FastAPI application: routers, request/response DTOs, middleware, and the composition root
that wires application services to their infrastructure adapters.

This package holds no business logic — see `CLAUDE.md` §5.1.

```bash
make dev     # infrastructure
make api     # this application, with reload, on http://localhost:8000
```

| Module            | Responsibility                                                        |
| ----------------- | --------------------------------------------------------------------- |
| `app.py`          | Application factory. Wires settings, logging, middleware and routers. |
| `middleware.py`   | Request identity, access logging, security headers, body size limit.  |
| `errors.py`       | The §36 error taxonomy and the §25.4 response envelope.               |
| `readiness.py`    | Registry of dependencies that `/ready` verifies.                      |
| `dependencies.py` | Dependency-injection conventions.                                     |
| `routers/`        | `health` (probes) and `v1` (versioned product routes).                |

See [`docs/api/README.md`](../../docs/api/README.md) for the API contract, and
[`docs/architecture/ARCHITECTURE.md`](../../docs/architecture/ARCHITECTURE.md) for the request
path.
