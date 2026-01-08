"""Tests for CLI column limiting functionality.

Tests the limit_columns() function and its integration with table rendering.
"""

from __future__ import annotations

from affinity.cli.render import (
    _ESSENTIAL_COLUMNS,
    _LONG_COLUMNS,
    _MIN_COL_WIDTH,
    format_duration,
    get_max_columns,
    get_terminal_width,
    limit_columns,
)


class TestLimitColumns:
    """Tests for the limit_columns() function."""

    def test_no_limiting_when_under_max(self) -> None:
        """When columns fit, return all columns unchanged."""
        columns = ["id", "name", "email"]
        result, omitted = limit_columns(columns, max_cols=10)
        assert result == ["id", "name", "email"]
        assert omitted == 0

    def test_limiting_drops_columns(self) -> None:
        """When over limit, drops non-essential columns."""
        columns = ["id", "a", "b", "c", "d", "e"]
        result, omitted = limit_columns(columns, max_cols=3)
        assert len(result) == 3
        assert "id" in result  # Essential is kept
        assert omitted == 3

    def test_preserves_original_order(self) -> None:
        """Selected columns maintain their original order."""
        columns = ["z", "id", "a", "b", "c"]
        result, omitted = limit_columns(columns, max_cols=3)
        # id is essential, z and a are first regular columns
        assert result == ["z", "id", "a"]
        assert omitted == 2

    def test_essential_columns_always_kept(self) -> None:
        """Essential columns (id, listentryid) are never dropped."""
        columns = ["a", "b", "id", "c", "listentryid", "d"]
        result, omitted = limit_columns(columns, max_cols=2)
        # Even though max_cols=2, both essential columns are kept
        assert "id" in result
        assert "listentryid" in result
        assert omitted == 4

    def test_droppable_columns_dropped_first(self) -> None:
        """Long/droppable columns are dropped before regular columns."""
        columns = ["id", "name", "description", "status", "notes", "type"]
        # description and notes are in _LONG_COLUMNS, should be dropped first
        result, omitted = limit_columns(columns, max_cols=4)
        assert "description" not in result
        assert "notes" not in result
        assert "id" in result
        assert "name" in result
        assert omitted == 2

    def test_custom_essential_columns(self) -> None:
        """Custom essential set is respected."""
        columns = ["a", "b", "c", "custom"]
        result, omitted = limit_columns(columns, max_cols=2, essential=frozenset({"custom"}))
        assert "custom" in result
        assert omitted == 2

    def test_custom_drop_first_columns(self) -> None:
        """Custom drop_first set is respected."""
        columns = ["a", "b", "c", "dropme"]
        result, omitted = limit_columns(columns, max_cols=3, drop_first=frozenset({"dropme"}))
        assert "dropme" not in result
        assert omitted == 1

    def test_empty_columns_list(self) -> None:
        """Empty input returns empty output."""
        result, omitted = limit_columns([], max_cols=10)
        assert result == []
        assert omitted == 0

    def test_case_insensitive_essential_match(self) -> None:
        """Essential column matching is case-insensitive."""
        columns = ["ID", "Name", "ListEntryId"]
        result, _omitted = limit_columns(columns, max_cols=2)
        # ID and ListEntryId should be matched case-insensitively
        assert "ID" in result
        assert "ListEntryId" in result

    def test_case_insensitive_droppable_match(self) -> None:
        """Droppable column matching is case-insensitive."""
        columns = ["id", "name", "DESCRIPTION", "Notes"]
        result, _omitted = limit_columns(columns, max_cols=2)
        # DESCRIPTION and Notes should be recognized as droppable
        assert "DESCRIPTION" not in result
        assert "Notes" not in result

    def test_edge_case_essential_exceeds_max(self) -> None:
        """When essential columns alone exceed max_cols, still keep them all."""
        columns = ["id", "listentryid", "a", "b"]
        result, omitted = limit_columns(columns, max_cols=1)
        # Both essential columns should still be kept
        assert "id" in result
        assert "listentryid" in result
        # Only regular columns are dropped
        assert omitted == 2


class TestGetMaxColumns:
    """Tests for get_max_columns() calculation."""

    def test_narrow_terminal(self) -> None:
        """Narrow terminal (80 chars) allows ~7 columns."""
        max_cols = get_max_columns(terminal_width=80)
        assert 6 <= max_cols <= 8

    def test_wide_terminal(self) -> None:
        """Wide terminal (200 chars) allows more columns."""
        max_cols = get_max_columns(terminal_width=200)
        assert max_cols > 15

    def test_very_narrow_terminal(self) -> None:
        """Very narrow terminal returns minimum of 4 columns."""
        max_cols = get_max_columns(terminal_width=20)
        assert max_cols >= 4

    def test_formula_uses_min_col_width(self) -> None:
        """Formula should account for borders and minimum column width."""
        # usable = width - 2 (outer borders)
        # max_cols = usable // (_MIN_COL_WIDTH + 3)
        width = 100
        expected = (width - 2) // (_MIN_COL_WIDTH + 3)
        assert get_max_columns(terminal_width=width) == max(4, expected)


class TestGetTerminalWidth:
    """Tests for get_terminal_width() helper."""

    def test_returns_positive_integer(self) -> None:
        """Should return a positive integer."""
        width = get_terminal_width()
        assert isinstance(width, int)
        assert width > 0


class TestFormatDuration:
    """Tests for format_duration() helper."""

    def test_seconds_only(self) -> None:
        """Formats seconds as 0:SS."""
        assert format_duration(45) == "0:45"
        assert format_duration(5) == "0:05"

    def test_minutes_and_seconds(self) -> None:
        """Formats minutes:seconds correctly."""
        assert format_duration(135) == "2:15"
        assert format_duration(62) == "1:02"

    def test_hours_minutes_seconds(self) -> None:
        """Formats hours:minutes:seconds correctly."""
        assert format_duration(3725) == "1:02:05"
        assert format_duration(7200) == "2:00:00"

    def test_fractional_seconds_truncated(self) -> None:
        """Fractional seconds are truncated."""
        assert format_duration(45.9) == "0:45"
        assert format_duration(45.1) == "0:45"


class TestConstants:
    """Tests for module-level constants."""

    def test_long_columns_is_frozenset(self) -> None:
        """_LONG_COLUMNS should be a frozenset for immutability."""
        assert isinstance(_LONG_COLUMNS, frozenset)

    def test_essential_columns_is_frozenset(self) -> None:
        """_ESSENTIAL_COLUMNS should be a frozenset for immutability."""
        assert isinstance(_ESSENTIAL_COLUMNS, frozenset)

    def test_essential_columns_contains_id(self) -> None:
        """Essential columns should include 'id'."""
        assert "id" in _ESSENTIAL_COLUMNS

    def test_essential_columns_contains_listentryid(self) -> None:
        """Essential columns should include 'listentryid'."""
        assert "listentryid" in _ESSENTIAL_COLUMNS

    def test_long_columns_contains_expected_fields(self) -> None:
        """Long columns should contain known long-content fields."""
        expected = {"description", "notes", "content", "fields"}
        assert expected.issubset(_LONG_COLUMNS)

    def test_min_col_width_is_reasonable(self) -> None:
        """Minimum column width should be reasonable (5-15 chars)."""
        assert 5 <= _MIN_COL_WIDTH <= 15
