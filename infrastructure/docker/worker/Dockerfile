# Built from the repository root (Milestone 26): `docker build -f infrastructure/docker/worker/Dockerfile .`
# The Temporal worker (`colt_workflows`) has no `apps/` directory of its own — it is a plain
# `uv` workspace package, run as `python -m colt_workflows` (Makefile's own `worker:` target) —
# so this Dockerfile lives alongside this repository's other infrastructure configuration
# rather than under `apps/`, where it would imply a directory structure that doesn't exist.

FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

FROM base AS builder
WORKDIR /workspace

COPY pyproject.toml uv.lock ./
COPY packages/python/ packages/python/
RUN uv sync --frozen --no-dev --package colt-workflows

FROM python:3.12-slim AS runtime
WORKDIR /workspace

RUN useradd --create-home --uid 1000 colt
COPY --from=builder /workspace /workspace
ENV PATH="/workspace/.venv/bin:$PATH"
USER colt

CMD ["python", "-m", "colt_workflows"]
