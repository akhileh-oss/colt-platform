"""The search provider port (CLAUDE.md §28.1, §28.2's `SearchProvider` category — `search_web`,
§16.1's Research tools).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    async def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]: ...
