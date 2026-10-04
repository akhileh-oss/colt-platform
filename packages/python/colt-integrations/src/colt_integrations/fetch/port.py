"""The fetch provider port (CLAUDE.md §28.1, §28.2's `ObjectStorageProvider`-adjacent category —
`fetch_page`, §16.1's Research tools).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FetchedDocument:
    url: str
    final_url: str
    status_code: int
    title: str | None
    text: str
    fetched_at: datetime


class FetchProvider(Protocol):
    async def fetch(self, url: str) -> FetchedDocument: ...
