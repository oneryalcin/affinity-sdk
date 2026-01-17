"""Tests for query output truncation functions.

Tests the format-aware truncation functions that preserve structure while
respecting byte limits.
"""

from __future__ import annotations

from affinity.cli.query.output import (
    truncate_csv_output,
    truncate_jsonl_output,
    truncate_markdown_output,
    truncate_toon_output,
)


class TestTruncateToonOutput:
    """Tests for truncate_toon_output() TOON envelope truncation."""

    def test_no_truncation_needed(self) -> None:
        """Content within limit returns unchanged."""
        content = "data[2]{id,name}:\n  1,Alice\n  2,Bob"
        result, was_truncated = truncate_toon_output(content, 1000)
        assert result == content
        assert was_truncated is False

    def test_basic_truncation(self) -> None:
        """Truncates data rows while preserving envelope."""
        rows = "\n".join([f"  {i},Name{i}" for i in range(100)])
        content = f"data[100]{{id,name}}:\n{rows}"

        result, was_truncated = truncate_toon_output(content, 200)

        assert was_truncated is True
        # Should have truncation section
        assert "truncation:" in result
        assert "rowsShown:" in result
        assert "rowsOmitted:" in result
        # Data header should have updated count
        assert "data[" in result

    def test_preserves_pagination_section(self) -> None:
        """Truncation preserves pagination envelope."""
        content = (
            "data[100]{id,name}:\n"
            + "\n".join([f"  {i},Name{i}" for i in range(100)])
            + "\npagination:\n  hasMore: true\n  total: 500"
        )

        result, was_truncated = truncate_toon_output(content, 300)

        assert was_truncated is True
        assert "pagination:" in result
        assert "hasMore: true" in result
        assert "total: 500" in result

    def test_preserves_included_sections(self) -> None:
        """Truncation preserves included entity sections."""
        content = (
            "data[100]{id,name}:\n"
            + "\n".join([f"  {i},Name{i}" for i in range(100)])
            + "\nincluded_companies[2]{id,name}:\n  100,Acme\n  101,Beta"
        )

        result, was_truncated = truncate_toon_output(content, 300)

        assert was_truncated is True
        assert "included_companies[2]{id,name}:" in result

    def test_anonymous_format_fallback(self) -> None:
        """Old anonymous format falls back to line truncation."""
        # Old format without 'data' prefix: [N]{...}:
        content = "[100]{id,name}:\n" + "\n".join([f"  {i},Name{i}" for i in range(100)])

        result, was_truncated = truncate_toon_output(content, 200)

        # Should still truncate even with old format (falls back)
        assert was_truncated is True
        assert len(result.encode()) <= 200


class TestTruncateMarkdownOutput:
    """Tests for truncate_markdown_output() markdown table truncation."""

    def test_no_truncation_needed(self) -> None:
        """Content within limit returns unchanged."""
        content = "| id | name |\n| --- | --- |\n| 1 | Alice |\n| 2 | Bob |"
        result, was_truncated = truncate_markdown_output(content, 1000)
        assert result == content
        assert was_truncated is False

    def test_basic_truncation(self) -> None:
        """Truncates rows while keeping header."""
        rows = "\n".join([f"| {i} | Name{i} |" for i in range(100)])
        content = f"| id | name |\n| --- | --- |\n{rows}"

        result, was_truncated = truncate_markdown_output(content, 200)

        assert was_truncated is True
        # Header preserved
        assert "| id | name |" in result
        assert "| --- | --- |" in result
        # Has truncation footer
        assert "...truncated" in result
        assert "rows shown" in result

    def test_preserves_original_total(self) -> None:
        """Truncation footer includes original total when provided."""
        rows = "\n".join([f"| {i} | Name{i} |" for i in range(100)])
        content = f"| id | name |\n| --- | --- |\n{rows}"

        result, was_truncated = truncate_markdown_output(content, 200, original_total=500)

        assert was_truncated is True
        assert "of 500" in result

    def test_malformed_input_fallback(self) -> None:
        """Non-markdown input falls back to byte truncation."""
        content = "This is not a markdown table at all" + "x" * 500

        result, was_truncated = truncate_markdown_output(content, 100)

        assert was_truncated is True
        assert len(result.encode()) <= 100


class TestTruncateJsonlOutput:
    """Tests for truncate_jsonl_output() JSONL truncation."""

    def test_no_truncation_needed(self) -> None:
        """Content within limit returns unchanged."""
        content = '{"id":1}\n{"id":2}\n'
        result, was_truncated = truncate_jsonl_output(content, 1000)
        assert result == content
        assert was_truncated is False

    def test_basic_truncation(self) -> None:
        """Truncates lines and adds truncation marker."""
        lines = [f'{{"id":{i},"name":"Name{i}"}}' for i in range(100)]
        content = "\n".join(lines) + "\n"

        result, was_truncated = truncate_jsonl_output(content, 200)

        assert was_truncated is True
        # Ends with truncation marker
        assert result.endswith('{"truncated":true}')

    def test_empty_content(self) -> None:
        """Empty content within limit returns unchanged."""
        result, was_truncated = truncate_jsonl_output("", 100)

        # Empty content fits in limit, no truncation
        assert was_truncated is False
        assert result == ""


class TestTruncateCsvOutput:
    """Tests for truncate_csv_output() CSV truncation."""

    def test_no_truncation_needed(self) -> None:
        """Content within limit returns unchanged."""
        content = "id,name\n1,Alice\n2,Bob\n"
        result, was_truncated = truncate_csv_output(content, 1000)
        assert result == content
        assert was_truncated is False

    def test_basic_truncation(self) -> None:
        """Truncates rows while keeping header."""
        rows = "\n".join([f"{i},Name{i}" for i in range(100)])
        content = f"id,name\n{rows}"

        result, was_truncated = truncate_csv_output(content, 100)

        assert was_truncated is True
        # Header preserved
        assert result.startswith("id,name\n")
        # Some data rows kept
        assert "0,Name0" in result

    def test_header_only_when_limit_tight(self) -> None:
        """Very tight limit keeps only header."""
        content = "id,name\n1,Alice\n2,Bob\n"

        result, was_truncated = truncate_csv_output(content, 20)

        assert was_truncated is True
        # Header preserved (8 bytes + newline = 9)
        assert "id,name" in result


class TestTruncationExitCode:
    """Tests for EXIT_TRUNCATED constant."""

    def test_exit_truncated_value(self) -> None:
        """EXIT_TRUNCATED is 100."""
        from affinity.cli.constants import EXIT_TRUNCATED

        assert EXIT_TRUNCATED == 100


class TestFormatIncludedTables:
    """Tests for format_included_tables() function (Option B display).

    Tests the separate table display for included relationship data.
    """

    def test_empty_included_returns_empty_string(self) -> None:
        """Empty included data returns empty string."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_included_tables

        result = QueryResult(data=[{"id": 1}], included={})
        output = format_included_tables(result)
        assert output == ""

    def test_none_included_returns_empty_string(self) -> None:
        """None included data returns empty string."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_included_tables

        result = QueryResult(data=[{"id": 1}])
        output = format_included_tables(result)
        assert output == ""

    def test_single_relationship_formats_as_table(self) -> None:
        """Single relationship formats as titled table."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_included_tables

        result = QueryResult(
            data=[{"id": 1}],
            included={
                "companies": [
                    {"id": 100, "name": "Acme Corp", "domain": "acme.com"},
                    {"id": 101, "name": "Beta Inc", "domain": "beta.io"},
                ]
            },
        )
        output = format_included_tables(result)

        assert "Included: companies" in output
        assert "Acme Corp" in output
        assert "Beta Inc" in output
        assert "acme.com" in output

    def test_multiple_relationships_formats_as_separate_tables(self) -> None:
        """Multiple relationships format as separate titled tables."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_included_tables

        result = QueryResult(
            data=[{"id": 1}],
            included={
                "companies": [{"id": 100, "name": "Acme Corp"}],
                "persons": [{"id": 200, "firstName": "Alice", "lastName": "Smith"}],
            },
        )
        output = format_included_tables(result)

        assert "Included: companies" in output
        assert "Included: persons" in output
        assert "Acme Corp" in output
        assert "Alice" in output

    def test_empty_relationship_is_skipped(self) -> None:
        """Empty relationship list is skipped."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_included_tables

        result = QueryResult(
            data=[{"id": 1}],
            included={
                "companies": [{"id": 100, "name": "Acme Corp"}],
                "empty_rel": [],  # Empty list should be skipped
            },
        )
        output = format_included_tables(result)

        assert "Included: companies" in output
        assert "Included: empty_rel" not in output

    def test_filters_excluded_columns(self) -> None:
        """Excluded columns (like list_entries, fields) are filtered out."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_included_tables

        result = QueryResult(
            data=[{"id": 1}],
            included={
                "companies": [
                    {
                        "id": 100,
                        "name": "Acme Corp",
                        "list_entries": [{"listId": 1}],  # Should be excluded
                        "fields": [{"fieldId": 2}],  # Should be excluded
                        "interaction_dates": {},  # Should be excluded
                    }
                ]
            },
        )
        output = format_included_tables(result)

        assert "Acme Corp" in output
        # Excluded columns should not appear (snake_case names)
        assert "list_entries" not in output
        assert "fields" not in output
        assert "interaction_dates" not in output
