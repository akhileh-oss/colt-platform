"""Export the FastAPI OpenAPI schema to a file, without starting a server.

Used by ``pnpm --filter @colt/api-client generate`` (CLAUDE.md §44) to produce the input for
``openapi-typescript``. Deterministic given the same source: it imports the application object
and reads ``app.openapi()`` directly, so nothing needs to be listening on a port.

Uses the process's normal settings resolution (``get_settings()``), same as running the API for
real. The schema is static route and type shape; it does not vary with environment, so there is
nothing to override here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Path to write the schema JSON to.")
    args = parser.parse_args()

    from colt_api.app import create_app

    schema = create_app().openapi()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote OpenAPI schema ({len(schema.get('paths', {}))} paths) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
