"""Readiness dependency registry (CLAUDE.md §57).

Liveness answers "is the process alive"; readiness answers "can it accept work". Keeping them
separate matters: if liveness depended on every external service, a transient database blip
would restart every pod instead of just draining traffic.

Milestone 02 registers no checks — the API has no required dependencies yet. Milestone 05
registers the database, Milestone 06 Temporal. The registry exists so those land as one call
each rather than as a rewrite of the health endpoint.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

#: A check returns None when healthy, or a short reason when not.
ReadinessCheck = Callable[[], Awaitable[str | None]]

_CHECK_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class CheckResult:
    name: str
    ready: bool
    detail: str | None = None


@dataclass
class ReadinessRegistry:
    """Required dependencies for this service to accept work."""

    _checks: dict[str, ReadinessCheck] = field(default_factory=dict)

    def register(self, name: str, check: ReadinessCheck) -> None:
        if name in self._checks:
            raise ValueError(f"A readiness check named {name!r} is already registered.")
        self._checks[name] = check

    def clear(self) -> None:
        self._checks.clear()

    @property
    def names(self) -> list[str]:
        return sorted(self._checks)

    async def run(self) -> list[CheckResult]:
        """Run every check concurrently. A check that hangs fails rather than blocking probes."""

        async def _run_one(name: str, check: ReadinessCheck) -> CheckResult:
            try:
                detail = await asyncio.wait_for(check(), timeout=_CHECK_TIMEOUT_SECONDS)
            except TimeoutError:
                return CheckResult(name, ready=False, detail="timed out")
            except Exception as exc:  # noqa: BLE001 - a failing dependency must degrade the
                # probe to "not ready", never crash it into a 500 (CLAUDE.md §57).
                return CheckResult(name, ready=False, detail=f"{type(exc).__name__}: {exc}")
            return CheckResult(name, ready=detail is None, detail=detail)

        return list(
            await asyncio.gather(*(_run_one(name, c) for name, c in sorted(self._checks.items())))
        )


#: Process-wide registry. Milestones 05 and 06 register their dependencies against it.
readiness_registry = ReadinessRegistry()
