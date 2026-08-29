# API documentation

The FastAPI-generated OpenAPI schema is the canonical API contract (`CLAUDE.md` §25.3). The
TypeScript client in `packages/typescript/api-client` is generated from it and is never hand-edited.

This directory holds narrative documentation that the schema cannot express: authentication flows,
pagination and filtering conventions, the error taxonomy (`CLAUDE.md` §36), rate limits (§79) and
versioning policy.

Populated in Milestone 02.
