# Built from the repository root (Milestone 26): `docker build -f apps/api/Dockerfile .` —
# this is a `uv` workspace (CLAUDE.md §4), so `colt-api`'s local path dependencies on
# `colt-config`/`colt-domain`/`colt-application`/etc. can only resolve with the whole workspace
# in the build context, not `apps/api/` alone.

FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

FROM base AS builder
WORKDIR /workspace

# Dependency layers before source, so an application-code-only change doesn't re-resolve the
# whole workspace's dependency graph.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/python/ packages/python/
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/api/ apps/api/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /workspace

# Least-privilege (CLAUDE.md §40): the application never runs as root.
RUN useradd --create-home --uid 1000 colt
COPY --from=builder /workspace /workspace
ENV PATH="/workspace/.venv/bin:$PATH"
USER colt

EXPOSE 8000
CMD ["python", "-m", "colt_api"]
