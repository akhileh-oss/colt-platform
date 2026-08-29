#!/usr/bin/env bash
# Fail if any git-tracked file contains a secret that is not already in .secrets.baseline.
#
# The baseline records reviewed, known-safe matches (CLAUDE.md §40: secret scanning).
# `detect-secrets-hook` is used rather than `scan` because it reports new findings without
# rewriting the baseline, so the check is read-only and safe to run in CI.
#
# To accept a new finding, run with --update and review the baseline diff before committing.
set -euo pipefail

cd "$(dirname "$0")/.."

BASELINE=".secrets.baseline"
EXCLUDE='^\.venv/|^node_modules/|^\.git/|pnpm-lock\.yaml|uv\.lock|^\.secrets\.baseline$'

if [[ "${1:-}" == "--update" ]]; then
  detect-secrets scan --exclude-files "$EXCLUDE" --baseline "$BASELINE"
  echo "Baseline updated. Review the diff before committing."
  exit 0
fi

if [[ ! -f "$BASELINE" ]]; then
  echo "FAIL: $BASELINE is missing. Create it with: scripts/check-secrets.sh --update" >&2
  exit 1
fi

# Scan every tracked file except the baseline itself and vendored/lock artifacts.
mapfile -t files < <(git ls-files | grep -Ev "$EXCLUDE")

if [[ ${#files[@]} -eq 0 ]]; then
  echo "FAIL: no tracked files to scan." >&2
  exit 1
fi

if ! detect-secrets-hook --baseline "$BASELINE" "${files[@]}"; then
  echo "" >&2
  echo "FAIL: a potential secret is not present in $BASELINE." >&2
  echo "Remove the secret, or if it is a reviewed false positive run:" >&2
  echo "  scripts/check-secrets.sh --update" >&2
  exit 1
fi

echo "detect-secrets: no new findings across ${#files[@]} tracked files."
