"""Tests for CLI date utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from affinity.cli.date_utils import chunk_date_range


@pytest.mark.req("CLI-DATE-UTILS")
class TestChunkDateRange:
    """Tests for chunk_date_range function."""

    def test_empty_range(self) -> None:
        """Empty range (start == end) produces no chunks."""
        start = end = datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert list(chunk_date_range(start, end)) == []

    def test_single_chunk_small_range(self) -> None:
        """Date range under 365 days produces single chunk."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 1, tzinfo=timezone.utc)
        chunks = list(chunk_date_range(start, end))
        assert len(chunks) == 1
        assert chunks[0] == (start, end)

    def test_exactly_365_days(self) -> None:
        """Exactly 365 days produces single chunk."""
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)  # 365 days later
        chunks = list(chunk_date_range(start, end))
        assert len(chunks) == 1
        assert chunks[0] == (start, end)

    def test_366_days_produces_two_chunks(self) -> None:
        """366 days produces 2 chunks."""
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=366)
        chunks = list(chunk_date_range(start, end))
        assert len(chunks) == 2

    def test_multiple_chunks_large_range(self) -> None:
        """Date range over 365 days produces multiple chunks."""
        start = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 1, tzinfo=timezone.utc)  # ~2.5 years
        chunks = list(chunk_date_range(start, end))
        assert len(chunks) == 3  # ~2.5 years = 3 chunks

    def test_chunks_are_contiguous(self) -> None:
        """Verify chunk boundaries are contiguous (no gaps or overlaps)."""
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 1, tzinfo=timezone.utc)
        chunks = list(chunk_date_range(start, end))
        for i in range(len(chunks) - 1):
            assert chunks[i][1] == chunks[i + 1][0], "Chunks must be contiguous"

    def test_final_chunk_ends_at_end(self) -> None:
        """Final chunk ends exactly at the requested end date."""
        start = datetime(2022, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 15, tzinfo=timezone.utc)
        chunks = list(chunk_date_range(start, end))
        assert chunks[-1][1] == end

    def test_first_chunk_starts_at_start(self) -> None:
        """First chunk starts exactly at the requested start date."""
        start = datetime(2022, 3, 15, tzinfo=timezone.utc)
        end = datetime(2024, 6, 15, tzinfo=timezone.utc)
        chunks = list(chunk_date_range(start, end))
        assert chunks[0][0] == start

    def test_custom_max_days(self) -> None:
        """Custom max_days parameter works correctly."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 4, 1, tzinfo=timezone.utc)  # 91 days
        # With max_days=30, should get 4 chunks (91 / 30 = 3.03)
        chunks = list(chunk_date_range(start, end, max_days=30))
        assert len(chunks) == 4
        # Verify each chunk is at most 30 days
        for chunk_start, chunk_end in chunks:
            assert (chunk_end - chunk_start).days <= 30
