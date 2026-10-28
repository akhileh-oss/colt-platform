#!/usr/bin/env bash
# Verify every local infrastructure service is actually serving (CLAUDE.md §6.1, Milestone 01).
#
# Container healthchecks gate startup ordering, but two images are distroless or shipped without
# one, so this script probes every service from the host. It is the authority on "health checks
# pass" — not `docker compose ps`.
set -uo pipefail

cd "$(dirname "$0")/.."

# localhost must never be routed through an HTTP proxy, which some environments set globally.
CURL=(curl --fail --silent --show-error --noproxy '*' --max-time 10 -o /dev/null)

PASS=0
FAIL=0

report() {
  local status="$1" name="$2" detail="$3"
  if [[ "$status" == "ok" ]]; then
    printf '  \033[32m✓\033[0m %-16s %s\n' "$name" "$detail"
    PASS=$((PASS + 1))
  else
    printf '  \033[31m✗\033[0m %-16s %s\n' "$name" "$detail"
    FAIL=$((FAIL + 1))
  fi
}

check_http() {
  local name="$1" url="$2"
  if "${CURL[@]}" "$url" 2>/dev/null; then
    report ok "$name" "$url"
  else
    report fail "$name" "$url unreachable"
  fi
}

check_exec() {
  local name="$1" service="$2"
  shift 2
  if docker compose exec -T "$service" "$@" >/dev/null 2>&1; then
    report ok "$name" "$*"
  else
    report fail "$name" "$* failed"
  fi
}

echo "Colt local infrastructure health"
echo

check_exec "postgres" postgres pg_isready -U colt -d colt
check_exec "redis" redis redis-cli ping
check_exec "temporal" temporal sh -c 'temporal operator cluster health --address $(hostname -i):7233'
check_http "temporal-ui" "http://localhost:${TEMPORAL_UI_PORT:-8080}/"
check_http "minio" "http://localhost:${MINIO_PORT:-9000}/minio/health/live"
# The research bucket must exist, or object storage is healthy but unusable.
check_exec "minio-bucket" minio sh -c 'mc alias set h http://127.0.0.1:9000 minioadmin minioadmin && mc ls h/colt-research'
check_http "mailpit" "http://localhost:${MAILPIT_UI_PORT:-8025}/readyz"
# Probing the realm, not just the port, proves the colt realm imported.
check_http "keycloak" "http://localhost:${KEYCLOAK_PORT:-8081}/realms/colt"
check_http "otel-collector" "http://localhost:${OTEL_HEALTH_PORT:-13133}/"

echo
if [[ $FAIL -gt 0 ]]; then
  echo "UNHEALTHY — ${PASS} passed, ${FAIL} failed."
  echo "Inspect with: make logs"
  exit 1
fi

echo "All ${PASS} services healthy."
