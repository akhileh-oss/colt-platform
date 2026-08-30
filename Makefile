# =============================================================================
# Colt — developer entry points (CLAUDE.md §101)
#
# Targets are added milestone by milestone. A target whose milestone has not
# landed yet fails loudly rather than silently reporting success (CLAUDE.md §0.4).
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

UV  ?= uv
PNPM ?= pnpm

.PHONY: help install dev down logs health api api-client web worker migrate migration seed \
        format lint typecheck test test-unit test-integration test-e2e \
        test-workflows eval security build check clean

help: ## Show available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
install: ## Install Python and Node dependencies
	$(UV) sync
	$(PNPM) install

# -----------------------------------------------------------------------------
# Local infrastructure (Milestone 01)
# -----------------------------------------------------------------------------
dev: ## Start the full local environment
	@scripts/dev-up.sh

down: ## Stop the local environment (volumes are preserved)
	docker compose down

logs: ## Tail local service logs
	docker compose logs -f

health: ## Verify every local service is serving
	@scripts/dev-health.sh

api: ## Run the API locally with reload (requires `make dev` for infrastructure)
	$(UV) run python -m colt_api

api-client: ## Regenerate the typed TypeScript client from the API's OpenAPI schema
	$(PNPM) --filter @colt/api-client generate

web: ## Run the web app locally with reload (requires `make dev` and `make api`)
	$(PNPM) --filter @colt/web dev

worker: ## Run the Temporal worker (requires `make dev` for infrastructure)
	$(UV) run python -m colt_workflows


# -----------------------------------------------------------------------------
# Database (Milestone 05)
# -----------------------------------------------------------------------------
migrate: ## Apply Alembic migrations
	cd packages/python/colt-db && $(UV) run alembic upgrade head

migration: ## Create a new Alembic revision (usage: make migration name="add leads table")
	cd packages/python/colt-db && $(UV) run alembic revision --autogenerate -m "$(name)"

seed: ## Load development seed data (two organizations, two Keycloak-linked users)
	$(UV) run python apps/api/scripts/seed_dev_data.py


# -----------------------------------------------------------------------------
# Quality gates
# -----------------------------------------------------------------------------
format: ## Format Python and TypeScript sources
	$(UV) run ruff format .
	$(UV) run ruff check --fix .
	$(PNPM) run format

lint: ## Lint Python and TypeScript sources
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(PNPM) run lint
	$(PNPM) run format:check

typecheck: ## Type-check Python (mypy strict) and TypeScript
	$(UV) run mypy
	$(PNPM) run typecheck

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
test: test-unit ## Run the default test suite

test-unit: ## Run unit tests (Python + TypeScript)
	$(UV) run pytest -m "not integration and not e2e and not workflows and not evals"
	$(PNPM) run test

test-integration: ## Run integration tests (requires `make dev` + `make migrate`)
	$(UV) run pytest -m integration

test-e2e: ## Run end-to-end browser tests (starts the API and web server itself)
	$(PNPM) exec playwright test

test-workflows: ## Run Temporal workflow tests (in-process time-skipping environment)
	$(UV) run pytest -m workflows

eval: ## Run AI evaluation suites
	@echo "NOT AVAILABLE — the AI evaluation system is delivered in Milestone 23."; exit 1


# -----------------------------------------------------------------------------
# Security (CLAUDE.md §40)
# -----------------------------------------------------------------------------
security: ## Scan dependencies and the working tree for secrets
# --skip-editable (rather than --strict) because the colt-* workspace packages are local
# and have no PyPI release to audit. Every third-party dependency is still audited.
	$(UV) run pip-audit --skip-editable
	$(PNPM) audit --audit-level moderate
	$(UV) run scripts/check-secrets.sh

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
build: ## Build all deployable artifacts
	$(PNPM) run build


# -----------------------------------------------------------------------------
# Aggregate
# -----------------------------------------------------------------------------
check: lint typecheck test security ## Run every non-destructive CI-quality check

clean: ## Remove build, cache and coverage artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov coverage.xml
	find . -name '*.tsbuildinfo' -not -path './node_modules/*' -delete 2>/dev/null || true
	rm -rf packages/typescript/*/dist
