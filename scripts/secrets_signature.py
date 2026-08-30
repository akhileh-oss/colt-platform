"""Print the set of (filename, hashed_secret, type) triples a detect-secrets baseline records.

Used by check-secrets.sh to tell a genuinely new finding apart from `detect-secrets-hook`
rewriting bookkeeping fields (line_number, generated_at) whenever a tracked file's line count
shifts. Deliberately excludes those two fields: they drift harmlessly and comparing them would
make an unrelated file edit look like a new secret.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    baseline = json.loads(Path(sys.argv[1]).read_text())
    pairs = sorted(
        f"{filename}:{result['hashed_secret']}:{result['type']}"
        for filename, results in baseline.get("results", {}).items()
        for result in results
    )
    print("\n".join(pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
