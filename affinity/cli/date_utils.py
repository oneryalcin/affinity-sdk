"""Date utilities for CLI commands."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from affinity.models.secondary import Interaction

MAX_CHUNK_DAYS = 365


@dataclass
class ChunkedFetchResult:
    """Result from chunked interaction fetching."""

    interactions: list[Interaction]
    chunks_processed: int


def chunk_date_range(
    start: datetime,
    end: datetime,
    max_days: int = MAX_CHUNK_DAYS,
) -> Iterator[tuple[datetime, datetime]]:
    """
    Split a date range into chunks of max_days.

    Yields (chunk_start, chunk_end) tuples.

    Note: Relies on API using exclusive end_time boundary.
    If an interaction has timestamp exactly at chunk boundary,
    it will appear in the later chunk (not both).
    """
    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=max_days), end)
        yield (current, chunk_end)
        current = chunk_end
