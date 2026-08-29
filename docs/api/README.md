# API documentation

The FastAPI-generated OpenAPI schema at `/openapi.json` is the canonical API contract
(`CLAUDE.md` §25.3). The TypeScript client in `packages/typescript/api-client` is generated from
it and never hand-edited.

Run the API with `make api` (infrastructure first, via `make dev`), then browse
http://localhost:8000/docs.

## Versioning

Product routes live under `/api/v1` (`CLAUDE.md` §25). A breaking change means a new version
module, never an in-place change to an existing one.

Probe endpoints — `/live` and `/ready` — sit deliberately **outside** the version prefix: they are
infrastructure, not a product contract, and must keep working across API versions.

| Route                 | Purpose                                                   |
| --------------------- | --------------------------------------------------------- |
| `GET /live`           | Liveness. Checks nothing external (`CLAUDE.md` §57).      |
| `GET /ready`          | Readiness. 503 when a registered dependency is unhealthy. |
| `GET /api/v1/meta`    | Service name, version and environment.                    |
| `GET /openapi.json`   | The contract. Served in every environment.                |
| `GET /docs`, `/redoc` | Interactive docs. Disabled in production.                 |

## Errors

Every failure returns one envelope (`CLAUDE.md` §25.4):

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Lead was not found.",
    "request_id": "req_4ee10c22c248483598036cd592988013",
    "details": null
  }
}
```

`code` is drawn from the §36 taxonomy: `VALIDATION_ERROR`, `AUTHENTICATION_ERROR`,
`AUTHORIZATION_ERROR`, `NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`,
`PROVIDER_REJECTED`, `TIMEOUT`, `DEPENDENCY_FAILURE`, `INTERNAL_ERROR`, `POLICY_DENIED`.

Responses never carry stack traces, provider messages or internal identifiers. A 500 says only
that something failed, and gives the `request_id` to look it up.

Raise `ColtError` (or a subclass such as `NotFoundError`) rather than `HTTPException`, so the
status, code and body stay consistent.

## Request IDs

Every request has one. It is returned in the `X-Request-ID` header and in every error body, and
appears on every log line emitted while handling that request (`CLAUDE.md` §92), so a user's
report of a failure is enough to find it.

An inbound `X-Request-ID` is honoured when it matches `[A-Za-z0-9_-]{1,128}`, letting a trace span
services. Anything else is **replaced**, not sanitised: the value reaches log output, and
salvaging part of a hostile string would splice attacker-chosen text into logs under a header
operators trust.

## Rate limiting

Not yet implemented. `CLAUDE.md` §79 requires it on authentication-sensitive, AI, research and
outbound endpoints; the limits are already configured under `RATE_LIMIT_`. Enforcement needs Redis
and an authenticated principal, so it lands with Milestone 04.

## Adding an endpoint

`CLAUDE.md` §113 is the acceptance standard. In short: typed request and response models, the
error envelope on failure paths, authorization enforced, tenancy enforced, tests, and the OpenAPI
contract regenerated for the client.
