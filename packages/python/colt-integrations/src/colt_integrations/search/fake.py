"""`FakeSearchProvider` — the test double CLAUDE.md §28.1 requires every adapter to have, and
`SearchSettings.provider`'s configured default (no real search provider has a key configured
anywhere in this environment, the same situation `colt_ai` is in with Anthropic). Deterministic
and explicit about it: it returns exactly the fixture results it was given for a query, never a
fabricated "plausible" result — §0.4 forbids pretending to have real data when there is none.
"""

from __future__ import annotations

from colt_integrations.search.port import SearchResult


class FakeSearchProvider:
    def __init__(self, results: dict[str, list[SearchResult]] | None = None) -> None:
        self._results = results or {}

    async def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        return self._results.get(query, [])[:max_results]
