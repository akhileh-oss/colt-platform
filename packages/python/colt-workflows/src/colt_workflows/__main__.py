"""Run the Temporal worker: ``python -m colt_workflows``."""

from __future__ import annotations

import asyncio
import signal

from colt_config import get_settings
from colt_observability import configure_logging
from colt_workflows.worker import run_worker


async def _run() -> None:
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    # SIGTERM (container stop) and SIGINT (Ctrl-C) both trigger the same graceful shutdown path
    # in run_worker — neither should drop an in-flight activity (§58).
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)
    await run_worker(shutdown_event=shutdown_event)


def main() -> None:
    settings = get_settings()
    configure_logging(
        level=settings.app.log_level, service_name=settings.observability.service_name
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
