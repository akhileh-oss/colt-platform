#!/usr/bin/env bash
# Fail if any git-tracked file contains a secret that is not already in .secrets.baseline.
#
# The baseline records reviewed, known-safe matches (CLAUDE.md §40: secret scanning).
# `detect-secrets-hook` is used rather than `scan` because it reports new findings without
# rewriting the baseline wholesale — but it still rewrites bookkeeping fields (line numbers,
# `generated_at`) whenever a tracked file's line count shifts, and treats that rewrite itself
# as a failure so a human notices and stages it. That behaviour is right for a pre-commit hook
# with a human watching, and wrong for `make check`: an edit to any file that happens to move
# an unrelated secret's line number would fail the whole gate for a reason that has nothing to
# do with secrets. So this script tells the two apart: it compares the *set* of (filename,
# hashed secret) pairs before and after. Only a genuinely new pair fails the check; a rewrite
# that leaves that set unchanged is bookkeeping and is staged automatically.
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

# The set of (filename, hashed_secret) pairs a baseline records — deliberately excluding
# line_number and generated_at, which drift harmlessly whenever any tracked file's line count
# changes.
signature() {
  python3 "$(dirname "$0")/secrets_signature.py" "$1"
}

before="$(signature "$BASELINE")"

# Scan every tracked file except the baseline itself and vendored/lock artifacts.
mapfile -t files < <(git ls-files | grep -Ev "$EXCLUDE")

if [[ ${#files[@]} -eq 0 ]]; then
  echo "FAIL: no tracked files to scan." >&2
  exit 1
fi

hook_status=0
detect-secrets-hook --baseline "$BASELINE" "${files[@]}" || hook_status=$?

after="$(signature "$BASELINE")"

if [[ "$before" == "$after" ]]; then
  # Either the hook passed outright, or it "failed" only by rewriting bookkeeping fields —
  # the set of actual secrets is unchanged either way. Stage whatever it touched and succeed.
  if git ls-files --error-unmatch "$BASELINE" >/dev/null 2>&1; then
    git add "$BASELINE"
  fi
  echo "detect-secrets: no new findings across ${#files[@]} tracked files."
  exit 0
fi

echo "" >&2
echo "FAIL: a potential secret is not present in $BASELINE." >&2
echo "Remove the secret, or if it is a reviewed false positive run:" >&2
echo "  scripts/check-secrets.sh --update" >&2
exit 1
