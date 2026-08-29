# Scripts

Developer and CI scripts. Each must be executable, `set -euo pipefail`, and safe to run repeatedly.

| Script             | Purpose                                                                  |
| ------------------ | ------------------------------------------------------------------------ |
| `check-secrets.sh` | Fail if a tracked file contains a secret absent from `.secrets.baseline` |
