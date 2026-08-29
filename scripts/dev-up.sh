#!/usr/bin/env bash
# One-command local environment (CLAUDE.md §6.2).
#
# Steps 3-6 of §6.2 — migrations, FastAPI, Temporal workers, Next.js — belong to Milestones
# 05, 02, 06 and 03. They are announced as pending rather than silently skipped, so this script
# never implies more is running than actually is (§0.4).
set -euo pipefail

cd "$(dirname "$0")/.."

fail() { printf '\033[31mERROR:\033[0m %s\n' "$1" >&2; exit 1; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# --- 1. Validate prerequisites ------------------------------------------------
step "Checking prerequisites"

command -v docker >/dev/null 2>&1 || fail "docker is not installed."
docker compose version >/dev/null 2>&1 || fail "the docker compose plugin is not available."
docker info >/dev/null 2>&1 || fail "the Docker daemon is not running. Start Docker and retry."
echo "  docker $(docker version --format '{{.Server.Version}}'), compose $(docker compose version --short)"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "  created .env from .env.example (placeholders only — fill in before using real providers)"
else
  echo "  .env present"
fi

# Local development must never perform real external side effects (§6.4).
for flag in FEATURE_REAL_EMAIL FEATURE_REAL_CRM FEATURE_REAL_CALENDAR FEATURE_REAL_SOCIAL; do
  value="$(grep -E "^${flag}=" .env | tail -1 | cut -d= -f2- || true)"
  if [[ -n "$value" && "$value" != "false" ]]; then
    fail "$flag is '$value' in .env. Local development must not perform real external side effects (CLAUDE.md §6.4)."
  fi
done
echo "  outbound side effects disabled"

# --- 2. Start containers ------------------------------------------------------
step "Starting infrastructure"
docker compose up -d --wait

step "Provisioning object storage"
docker compose run --rm minio-init

# --- Health -------------------------------------------------------------------
step "Verifying health"
scripts/dev-health.sh

# --- 3-6. Pending milestones --------------------------------------------------
step "Not yet running"
cat <<'PENDING'
  database migrations   Milestone 05
  Temporal workers      Milestone 06
  Web (Next.js)         Milestone 03

  The API is built but not containerised: run it alongside this stack with `make api`.
PENDING

# --- 7. Expose local service URLs (§6.3) --------------------------------------
step "Local services"
cat <<URLS
  Web             http://localhost:3000              (Milestone 03)
  API             http://localhost:8000              (Milestone 02)
  API docs        http://localhost:8000/docs         (Milestone 02)
  Temporal UI     http://localhost:${TEMPORAL_UI_PORT:-8080}
  Mailpit UI      http://localhost:${MAILPIT_UI_PORT:-8025}
  MinIO console   http://localhost:${MINIO_CONSOLE_PORT:-9001}    (minioadmin / minioadmin)
  Keycloak        http://localhost:${KEYCLOAK_PORT:-8081}         (admin / admin)
  Postgres        postgresql://colt:colt@localhost:${POSTGRES_PORT:-5432}/colt
  Redis           redis://localhost:${REDIS_PORT:-6379}/0
  OTLP gRPC       http://localhost:${OTEL_GRPC_PORT:-4317}
URLS
echo
echo "Stop with: make down"
