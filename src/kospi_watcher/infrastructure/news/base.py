"""News provider contracts.

A ``NewsItem`` is a single dated headline. Providers must never raise from
``fetch`` — they return ``[]`` on failure so scraping degrades safely.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict


class NewsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str
    source: str
    topic: str
    published_at: AwareDatetime
    summary: str | None = None


def make_item_id(url: str, title: str) -> str:
    """Stable id from the canonical URL (falls back to the title)."""
    basis = url or title
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


@runtime_checkable
class NewsProvider(Protocol):
    name: str

    async def fetch(self, topic: str, *, as_of: datetime | None = None) -> Sequence[NewsItem]: ...
