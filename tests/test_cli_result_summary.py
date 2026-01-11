"""Tests for CLI ResultSummary rendering."""

from __future__ import annotations

from datetime import datetime

from affinity.cli.render import _build_row_segment, _render_summary_footer
from affinity.cli.results import DateRange, ResultSummary


class TestBuildRowSegment:
    """Tests for _build_row_segment helper function."""

    def test_none_total_rows_returns_none(self) -> None:
        summary = ResultSummary()
        assert _build_row_segment(summary, verbosity=0) is None

    def test_singular_row(self) -> None:
        summary = ResultSummary(total_rows=1)
        result = _build_row_segment(summary, verbosity=0)
        assert result == "1 row"

    def test_plural_rows(self) -> None:
        summary = ResultSummary(total_rows=150)
        result = _build_row_segment(summary, verbosity=0)
        assert result == "150 rows"

    def test_zero_rows(self) -> None:
        summary = ResultSummary(total_rows=0)
        result = _build_row_segment(summary, verbosity=0)
        assert result == "0 rows"

    def test_large_number_with_commas(self) -> None:
        summary = ResultSummary(total_rows=1234567)
        result = _build_row_segment(summary, verbosity=0)
        assert result == "1,234,567 rows"

    def test_type_breakdown_single_type_default_verbosity(self) -> None:
        # Single type at default verbosity should NOT show breakdown
        summary = ResultSummary(total_rows=50, type_breakdown={"email": 50})
        result = _build_row_segment(summary, verbosity=0)
        assert result == "50 rows"

    def test_type_breakdown_single_type_verbose(self) -> None:
        # Single type at verbosity >= 1 should show breakdown
        summary = ResultSummary(total_rows=50, type_breakdown={"email": 50})
        result = _build_row_segment(summary, verbosity=1)
        assert result == "50 rows: 50 email"

    def test_type_breakdown_multiple_types(self) -> None:
        # Multiple types should always show breakdown (sorted alphabetically)
        summary = ResultSummary(total_rows=150, type_breakdown={"email": 120, "call": 30})
        result = _build_row_segment(summary, verbosity=0)
        assert result == "150 rows: 30 call, 120 email"

    def test_scanned_rows_when_greater(self) -> None:
        summary = ResultSummary(total_rows=35, scanned_rows=9340)
        result = _build_row_segment(summary, verbosity=0)
        assert result == "35 rows from 9,340 scanned"

    def test_scanned_rows_not_shown_when_equal(self) -> None:
        summary = ResultSummary(total_rows=100, scanned_rows=100)
        result = _build_row_segment(summary, verbosity=0)
        assert result == "100 rows"

    def test_type_breakdown_takes_precedence_over_scanned(self) -> None:
        # When both are present, type_breakdown is shown (mutual exclusivity)
        summary = ResultSummary(
            total_rows=150,
            type_breakdown={"email": 120, "call": 30},
            scanned_rows=500,
        )
        result = _build_row_segment(summary, verbosity=0)
        assert result == "150 rows: 30 call, 120 email"
        assert "scanned" not in result


class TestRenderSummaryFooter:
    """Tests for _render_summary_footer function."""

    def test_none_summary_returns_none(self) -> None:
        assert _render_summary_footer(None) is None

    def test_empty_summary_returns_none(self) -> None:
        summary = ResultSummary()
        assert _render_summary_footer(summary) is None

    def test_row_count_only(self) -> None:
        summary = ResultSummary(total_rows=150)
        text = _render_summary_footer(summary)
        assert text is not None
        assert text.plain == "(150 rows)"

    def test_singular_row(self) -> None:
        summary = ResultSummary(total_rows=1)
        text = _render_summary_footer(summary)
        assert text is not None
        assert text.plain == "(1 row)"

    def test_zero_rows(self) -> None:
        summary = ResultSummary(total_rows=0)
        text = _render_summary_footer(summary)
        assert text is not None
        assert text.plain == "(0 rows)"

    def test_with_type_breakdown(self) -> None:
        summary = ResultSummary(total_rows=150, type_breakdown={"email": 120, "call": 30})
        text = _render_summary_footer(summary)
        assert text is not None
        assert "150 rows" in text.plain
        assert "120 email" in text.plain
        assert "30 call" in text.plain

    def test_with_date_range(self) -> None:
        summary = ResultSummary(
            total_rows=50,
            date_range=DateRange(start=datetime(2023, 7, 26), end=datetime(2026, 1, 11)),
        )
        text = _render_summary_footer(summary)
        assert text is not None
        assert "2023-07-26 → 2026-01-11" in text.plain

    def test_with_scanned_rows(self) -> None:
        summary = ResultSummary(total_rows=35, scanned_rows=9340)
        text = _render_summary_footer(summary)
        assert text is not None
        assert "35 rows from 9,340 scanned" in text.plain

    def test_with_included_counts(self) -> None:
        summary = ResultSummary(
            total_rows=50,
            included_counts={"companies": 10, "opportunities": 5},
        )
        text = _render_summary_footer(summary)
        assert text is not None
        assert "included:" in text.plain
        assert "10 companies" in text.plain
        assert "5 opportunities" in text.plain

    def test_chunks_not_shown_at_default_verbosity(self) -> None:
        summary = ResultSummary(total_rows=20, chunks_processed=4)
        text = _render_summary_footer(summary, verbosity=0)
        assert text is not None
        assert "chunks" not in text.plain

    def test_chunks_shown_at_verbose(self) -> None:
        summary = ResultSummary(total_rows=20, chunks_processed=4)
        text = _render_summary_footer(summary, verbosity=1)
        assert text is not None
        assert "4 chunks" in text.plain

    def test_custom_text(self) -> None:
        summary = ResultSummary(total_rows=10, custom_text="use --json for details")
        text = _render_summary_footer(summary)
        assert text is not None
        assert "use --json for details" in text.plain

    def test_full_combination(self) -> None:
        """Test all segments combined."""
        summary = ResultSummary(
            total_rows=150,
            type_breakdown={"email": 120, "call": 30},
            date_range=DateRange(start=datetime(2023, 7, 26), end=datetime(2026, 1, 11)),
        )
        text = _render_summary_footer(summary)
        assert text is not None
        assert text.plain == "(150 rows: 30 call, 120 email | 2023-07-26 → 2026-01-11)"

    def test_segments_joined_with_pipe(self) -> None:
        summary = ResultSummary(
            total_rows=50,
            date_range=DateRange(start=datetime(2024, 1, 1), end=datetime(2024, 12, 31)),
        )
        text = _render_summary_footer(summary)
        assert text is not None
        assert " | " in text.plain

    def test_style_is_dim(self) -> None:
        summary = ResultSummary(total_rows=100)
        text = _render_summary_footer(summary)
        assert text is not None
        assert text.style == "dim"


class TestDateRange:
    """Tests for DateRange model."""

    def test_format_display(self) -> None:
        dr = DateRange(start=datetime(2023, 7, 26), end=datetime(2026, 1, 11))
        assert dr.format_display() == "2023-07-26 → 2026-01-11"

    def test_format_display_same_day(self) -> None:
        dr = DateRange(start=datetime(2024, 6, 15), end=datetime(2024, 6, 15))
        assert dr.format_display() == "2024-06-15 → 2024-06-15"

    def test_json_serialization(self) -> None:
        dr = DateRange(start=datetime(2023, 7, 26, 10, 30, 0), end=datetime(2026, 1, 11, 15, 45, 0))
        data = dr.model_dump(mode="json")
        # Should serialize as ISO format strings
        assert "2023-07-26" in data["start"]
        assert "2026-01-11" in data["end"]


class TestResultSummary:
    """Tests for ResultSummary model."""

    def test_default_values(self) -> None:
        summary = ResultSummary()
        assert summary.total_rows is None
        assert summary.date_range is None
        assert summary.type_breakdown is None
        assert summary.included_counts is None
        assert summary.chunks_processed is None
        assert summary.scanned_rows is None
        assert summary.custom_text is None

    def test_json_serialization_with_aliases(self) -> None:
        summary = ResultSummary(
            total_rows=100,
            type_breakdown={"email": 80, "call": 20},
            chunks_processed=5,
        )
        data = summary.model_dump(by_alias=True, mode="json")
        assert data["totalRows"] == 100
        assert data["typeBreakdown"] == {"email": 80, "call": 20}
        assert data["chunksProcessed"] == 5

    def test_nested_date_range_serialization(self) -> None:
        summary = ResultSummary(
            total_rows=50,
            date_range=DateRange(start=datetime(2024, 1, 1), end=datetime(2024, 12, 31)),
        )
        data = summary.model_dump(by_alias=True, mode="json")
        assert "dateRange" in data
        assert data["dateRange"] is not None
        assert "start" in data["dateRange"]
        assert "end" in data["dateRange"]
