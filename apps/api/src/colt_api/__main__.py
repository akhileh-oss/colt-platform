"""Run the API with uvicorn: ``python -m colt_api``."""

from __future__ import annotations

import uvicorn

from colt_config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "colt_api.app:app",
        host="0.0.0.0",  # noqa: S104 - binding all interfaces is required inside a container
        port=8000,
        reload=settings.app.debug,
        log_config=None,  # colt-observability owns logging configuration
    )


if __name__ == "__main__":
    main()
