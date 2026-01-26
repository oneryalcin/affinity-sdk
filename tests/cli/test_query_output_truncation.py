"""Tests for query output truncation functions.

Tests the format-aware truncation functions that preserve structure while
respecting byte limits.
"""

from __future__ import annotations

import json

from affinity.cli.query.output import (
    format_json,
    truncate_csv_output,
    truncate_json_result,
    truncate_jsonl_output,
    truncate_markdown_output,
    truncate_toon_output,
)


class TestTruncateJsonResult:
    """Tests for truncate_json_result() - object-level JSON truncation."""

    def _make_result(
        self, data: list, included: dict | None = None, pagination: dict | None = None
    ):
        """Helper to create QueryResult for testing."""
        from affinity.cli.query.models import QueryResult

        return QueryResult(data=data, included=included or {}, pagination=pagination)

    def test_no_truncation_needed(self) -> None:
        """Data within limit returns unchanged."""
        result = self._make_result([{"id": 1}, {"id": 2}])
        original_data = result.data.copy()

        result, items_kept, was_truncated = truncate_json_result(result, 1000)

        assert result.data == original_data
        assert items_kept == 2
        assert was_truncated is False

    def test_truncates_data_array(self) -> None:
        """Large data array is truncated to fit limit."""
        data = [{"id": i, "name": f"Name{i}"} for i in range(100)]
        result = self._make_result(data)

        result, items_kept, was_truncated = truncate_json_result(result, 500)

        assert was_truncated is True
        assert items_kept < 100
        assert len(result.data) == items_kept
        # Verify serialized output fits
        output = format_json(result, pretty=False)
        assert len(output.encode()) <= 500
        # Verify valid JSON
        json.loads(output)

    def test_preserves_envelope(self) -> None:
        """Non-data fields (included, pagination) are preserved."""
        data = [{"id": i} for i in range(100)]
        included = {"companies": [{"id": 1, "name": "Acme"}]}
        pagination = {"hasMore": True, "total": 500}
        result = self._make_result(data, included=included, pagination=pagination)

        result, _items_kept, was_truncated = truncate_json_result(result, 500)

        assert was_truncated is True
        assert result.included == included  # Preserved
        assert result.pagination == pagination  # Preserved
        output = format_json(result, pretty=False)
        output_obj = json.loads(output)
        assert "included" in output_obj
        assert "pagination" in output_obj

    def test_empty_data_array(self) -> None:
        """Empty data array returns unchanged."""
        result = self._make_result([])

        result, items_kept, was_truncated = truncate_json_result(result, 100)

        assert was_truncated is False
        assert items_kept == 0

    def test_cant_truncate_envelope_too_large(self) -> None:
        """When envelope alone exceeds limit, return unchanged with was_truncated=False."""
        # Large included section that exceeds limit on its own
        included = {"companies": [{"id": i, "name": f"Company{i}" * 100} for i in range(10)]}
        result = self._make_result([{"id": 1}], included=included)

        _result, _items_kept, was_truncated = truncate_json_result(result, 100)

        # Can't truncate - envelope too large
        assert was_truncated is False

    def test_empty_data_with_large_envelope(self) -> None:
        """Empty data with large envelope returns was_truncated=False (caller must handle)."""
        # Edge case from Review 3: empty data but huge included section
        included = {"companies": [{"id": i, "name": f"Company{i}" * 100} for i in range(10)]}
        result = self._make_result([], included=included)

        result, items_kept, was_truncated = truncate_json_result(result, 100)

        # Can't truncate empty data - caller (query_cmd.py) must check size and error
        assert was_truncated is False
        assert items_kept == 0

    def test_output_never_exceeds_limit(self) -> None:
        """Final output must never exceed max_bytes when truncation succeeds."""
        data = [{"id": i, "name": f"LongName{i}" * 10} for i in range(1000)]

        for max_bytes in [500, 1000, 5000, 10000]:
            result_copy = self._make_result(data.copy())
            result_copy, _items_kept, was_truncated = truncate_json_result(result_copy, max_bytes)
            if was_truncated:
                output = format_json(result_copy, pretty=False)
                assert len(output.encode()) <= max_bytes

    def test_precision_preserved(self) -> None:
        """Numeric precision is preserved (no parse/re-serialize round-trip)."""
        # Use numbers that could lose precision in JSON round-trip
        data = [
            {"id": 1, "value": 1.0000000000000001},
            {"id": 2, "value": 9999999999999999},
        ]
        result = self._make_result(data)

        result, _items_kept, _was_truncated = truncate_json_result(result, 10000)

        # Values should be exactly preserved (truncation operates on Python objects)
        assert result.data[0]["value"] == 1.0000000000000001
        assert result.data[1]["value"] == 9999999999999999

    def test_with_include_meta(self) -> None:
        """Truncation respects include_meta parameter."""
        from affinity.cli.results import ResultSummary

        data = [{"id": i, "name": f"Name{i}"} for i in range(100)]
        result = self._make_result(data)
        result.summary = ResultSummary(fetched=100, returned=100, filtered=0, rate_limited=0)
        result.meta = {"executionTime": 1.5}

        # Truncate with include_meta=True - should account for larger output size
        result, _items_kept, was_truncated = truncate_json_result(result, 500, include_meta=True)

        assert was_truncated is True
        output = format_json(result, pretty=False, include_meta=True)
        assert len(output.encode()) <= 500

    def test_binary_search_finds_optimal(self) -> None:
        """Binary search finds maximum items that fit."""
        # Create data where each item is ~50 bytes
        data = [{"id": i, "name": f"Name{i:04d}"} for i in range(100)]
        result = self._make_result(data)

        # Set limit that should fit ~10 items
        result, items_kept, was_truncated = truncate_json_result(result, 600)

        assert was_truncated is True
        # Verify we kept as many as possible
        output = format_json(result, pretty=False)
        assert len(output.encode()) <= 600
        # Adding one more should exceed limit
        if items_kept < len(data):
            result.data = data[: items_kept + 1]
            test_output = format_json(result, pretty=False)
            assert len(test_output.encode()) > 600


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


class TestDisplayValue:
    """Tests for _display_value() helper function.

    Tests the display value extraction priority: name → firstName lastName → title → email → id
    """

    def test_display_value_with_name(self) -> None:
        """Record with 'name' field uses it."""
        from affinity.cli.query.output import _display_value

        assert _display_value({"name": "Acme Corp", "id": 123}) == "Acme Corp"

    def test_display_value_with_person(self) -> None:
        """Record with firstName/lastName shows 'firstName lastName'."""
        from affinity.cli.query.output import _display_value

        assert _display_value({"firstName": "John", "lastName": "Smith", "id": 123}) == "John Smith"

    def test_display_value_with_first_name_only(self) -> None:
        """Record with only firstName shows just firstName."""
        from affinity.cli.query.output import _display_value

        assert _display_value({"firstName": "John", "id": 123}) == "John"

    def test_display_value_with_title_fallback(self) -> None:
        """Record without name/firstName uses title."""
        from affinity.cli.query.output import _display_value

        assert _display_value({"title": "CEO", "id": 123}) == "CEO"

    def test_display_value_with_email_fallback(self) -> None:
        """Record without name/firstName/title uses email."""
        from affinity.cli.query.output import _display_value

        assert _display_value({"email": "john@example.com", "id": 123}) == "john@example.com"

    def test_display_value_with_id_fallback(self) -> None:
        """Record with only id shows '<unknown> (id)'."""
        from affinity.cli.query.output import _display_value

        assert _display_value({"id": 123}) == "<unknown> (123)"

    def test_display_value_with_none(self) -> None:
        """None record shows '<unknown>'."""
        from affinity.cli.query.output import _display_value

        assert _display_value(None) == "<unknown>"

    def test_display_value_empty_record(self) -> None:
        """Empty record shows '<unknown>'."""
        from affinity.cli.query.output import _display_value

        assert _display_value({}) == "<unknown>"

    def test_display_value_name_takes_priority(self) -> None:
        """'name' takes priority over firstName."""
        from affinity.cli.query.output import _display_value

        result = _display_value(
            {"name": "Company Inc", "firstName": "John", "email": "x@y.com", "id": 1}
        )
        assert result == "Company Inc"


class TestExpandIncludes:
    """Tests for expand_includes() function.

    Tests inline expansion of included data into parent records.
    """

    def test_expand_includes_basic(self) -> None:
        """Basic expansion adds included.{rel} column."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        included_by_parent = {
            "companies": {
                1: [{"id": 100, "name": "Acme Corp"}],
                2: [{"id": 101, "name": "Beta Inc"}],
            }
        }

        result = expand_includes(data, included_by_parent)

        assert len(result) == 2
        assert result[0]["included.companies"] == ["Acme Corp"]
        assert result[1]["included.companies"] == ["Beta Inc"]

    def test_expand_includes_multiple_related(self) -> None:
        """Multiple related records become list of display values."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]
        included_by_parent = {
            "companies": {
                1: [
                    {"id": 100, "name": "Acme Corp"},
                    {"id": 101, "name": "Beta Inc"},
                ]
            }
        }

        result = expand_includes(data, included_by_parent)

        assert result[0]["included.companies"] == ["Acme Corp", "Beta Inc"]

    def test_expand_includes_no_included_data(self) -> None:
        """Empty included_by_parent returns original data unchanged."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]

        result = expand_includes(data, None)
        assert result == data

        result = expand_includes(data, {})
        assert result == data

    def test_expand_includes_missing_parent_id(self) -> None:
        """Missing parent in mapping shows empty list."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        included_by_parent = {
            "companies": {
                1: [{"id": 100, "name": "Acme Corp"}],
                # Note: no entry for parent id=2
            }
        }

        result = expand_includes(data, included_by_parent)

        assert result[0]["included.companies"] == ["Acme Corp"]
        assert result[1]["included.companies"] == []  # Empty list for missing parent

    def test_expand_includes_multiple_relationships(self) -> None:
        """Multiple relationships each get their own column."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Acme Corp"}]
        included_by_parent = {
            "persons": {1: [{"firstName": "Alice", "lastName": "Smith"}]},
            "opportunities": {1: [{"name": "Big Deal"}]},
        }

        result = expand_includes(data, included_by_parent)

        assert result[0]["included.persons"] == ["Alice Smith"]
        assert result[0]["included.opportunities"] == ["Big Deal"]

    def test_expand_includes_does_not_mutate_original(self) -> None:
        """Original data is not mutated."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]
        original_keys = set(data[0].keys())
        included_by_parent = {"companies": {1: [{"id": 100, "name": "Acme Corp"}]}}

        expand_includes(data, included_by_parent)

        # Original should not have the included column
        assert set(data[0].keys()) == original_keys

    def test_expand_includes_with_unknown_records(self) -> None:
        """Records with no display fields show '<unknown> (id)'."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]
        included_by_parent = {
            "companies": {1: [{"id": 999}]}  # Only has id, no name
        }

        result = expand_includes(data, included_by_parent)

        assert result[0]["included.companies"] == ["<unknown> (999)"]


class TestDisplayValueCustomFields:
    """Tests for _display_value() with custom display fields (Phase 2)."""

    def test_custom_display_fields_single(self) -> None:
        """Custom display field is used instead of default fallback."""
        from affinity.cli.query.output import _display_value

        record = {"id": 100, "name": "Acme Corp", "domain": "acme.com"}
        result = _display_value(record, display_fields=["domain"])
        assert result == "acme.com"

    def test_custom_display_fields_multiple(self) -> None:
        """Multiple custom display fields are joined with space."""
        from affinity.cli.query.output import _display_value

        record = {"id": 100, "name": "Acme Corp", "domain": "acme.com", "industry": "Tech"}
        result = _display_value(record, display_fields=["name", "domain"])
        assert result == "Acme Corp acme.com"

    def test_custom_display_fields_partial(self) -> None:
        """Only non-empty custom fields are included."""
        from affinity.cli.query.output import _display_value

        record = {"id": 100, "name": "Acme Corp", "domain": None}
        result = _display_value(record, display_fields=["name", "domain"])
        assert result == "Acme Corp"

    def test_custom_display_fields_all_missing_falls_back(self) -> None:
        """Falls back to default chain when all custom fields are missing."""
        from affinity.cli.query.output import _display_value

        record = {"id": 100, "name": "Acme Corp"}
        # custom fields don't exist, falls back to default chain
        result = _display_value(record, display_fields=["nonexistent", "also_missing"])
        assert result == "Acme Corp"  # Falls back to name

    def test_custom_display_fields_empty_string_skipped(self) -> None:
        """Empty string values are skipped."""
        from affinity.cli.query.output import _display_value

        record = {"id": 100, "name": "", "domain": "acme.com"}
        result = _display_value(record, display_fields=["name", "domain"])
        assert result == "acme.com"


class TestExpandIncludesCustomDisplayFields:
    """Tests for expand_includes() with custom display fields from include_configs."""

    def test_expand_with_include_configs(self) -> None:
        """Custom display fields from include_configs are used."""
        from affinity.cli.query.models import IncludeConfig
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]
        included_by_parent = {
            "companies": {1: [{"id": 100, "name": "Acme Corp", "domain": "acme.com"}]}
        }
        include_configs = {"companies": IncludeConfig(display=["domain"])}

        result = expand_includes(data, included_by_parent, include_configs=include_configs)

        # Should show domain instead of name
        assert result[0]["included.companies"] == ["acme.com"]

    def test_expand_with_include_configs_dict_form(self) -> None:
        """Include configs as dict (from JSON) work correctly."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]
        included_by_parent = {
            "companies": {1: [{"id": 100, "name": "Acme Corp", "domain": "acme.com"}]}
        }
        # Dict form (as parsed from JSON before conversion to IncludeConfig)
        include_configs = {"companies": {"display": ["domain", "name"]}}

        result = expand_includes(data, included_by_parent, include_configs=include_configs)

        # Should show domain and name
        assert result[0]["included.companies"] == ["acme.com Acme Corp"]

    def test_expand_uses_schema_defaults_when_no_config(self) -> None:
        """Falls back to schema display_fields when include_configs is empty."""
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]
        included_by_parent = {
            "companies": {1: [{"id": 100, "name": "Acme Corp", "domain": "acme.com"}]}
        }

        # source_entity="persons" triggers schema lookup
        # persons->companies relationship has display_fields=("name",)
        result = expand_includes(
            data, included_by_parent, include_configs=None, source_entity="persons"
        )

        # Should use schema default (name) for companies relationship
        assert result[0]["included.companies"] == ["Acme Corp"]

    def test_expand_config_overrides_schema_default(self) -> None:
        """Custom include_configs override schema display_fields."""
        from affinity.cli.query.models import IncludeConfig
        from affinity.cli.query.output import expand_includes

        data = [{"id": 1, "name": "Alice"}]
        included_by_parent = {
            "companies": {1: [{"id": 100, "name": "Acme Corp", "domain": "acme.com"}]}
        }
        # Custom config should override schema default
        include_configs = {"companies": IncludeConfig(display=["domain"])}

        result = expand_includes(
            data, included_by_parent, include_configs=include_configs, source_entity="persons"
        )

        # Should use custom config (domain), not schema default (name)
        assert result[0]["included.companies"] == ["acme.com"]


class TestIncludeConfigModel:
    """Tests for IncludeConfig Pydantic model and normalize_include validator."""

    def test_include_config_with_display(self) -> None:
        """IncludeConfig parses display field correctly."""
        from affinity.cli.query.models import IncludeConfig

        config = IncludeConfig(display=["name", "domain"])
        assert config.display == ["name", "domain"]

    def test_include_config_without_display(self) -> None:
        """IncludeConfig allows None display."""
        from affinity.cli.query.models import IncludeConfig

        config = IncludeConfig()
        assert config.display is None

    def test_normalize_include_simple_list(self) -> None:
        """Simple list format is normalized to dict."""
        from affinity.cli.query.models import Query

        query = Query.model_validate({"from": "persons", "include": ["companies", "opportunities"]})
        assert query.include is not None
        assert "companies" in query.include
        assert "opportunities" in query.include
        assert query.include["companies"].display is None

    def test_normalize_include_extended_dict(self) -> None:
        """Extended dict format is parsed correctly."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {"from": "persons", "include": {"companies": {"display": ["name", "domain"]}}}
        )
        assert query.include is not None
        assert query.include["companies"].display == ["name", "domain"]

    def test_normalize_include_mixed_list(self) -> None:
        """Mixed list format (strings and dicts) is normalized."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {"from": "persons", "include": ["companies", {"opportunities": {"display": ["name"]}}]}
        )
        assert query.include is not None
        assert "companies" in query.include
        assert "opportunities" in query.include
        assert query.include["companies"].display is None
        assert query.include["opportunities"].display == ["name"]

    def test_normalize_include_null_config(self) -> None:
        """Null config in dict is normalized to empty config."""
        from affinity.cli.query.models import Query

        query = Query.model_validate({"from": "persons", "include": {"companies": None}})
        assert query.include is not None
        assert query.include["companies"].display is None


class TestIncludeStyleOption:
    """Tests for --include-style CLI option behavior in format_table()."""

    def test_ids_only_style_shows_raw_ids(self) -> None:
        """ids-only style doesn't expand, shows raw organizationIds."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_table

        result = QueryResult(
            data=[{"id": 1, "firstName": "Alice", "organizationIds": [100, 101]}],
            included={"companies": [{"id": 100, "name": "Acme"}]},
            included_by_parent={"companies": {1: [{"id": 100, "name": "Acme"}]}},
        )

        output = format_table(result, include_style="ids-only")

        # Should show raw IDs, not expanded names
        assert "100" in output
        assert "101" in output
        # Should not have expanded column or separate tables
        assert "included.compan" not in output
        assert "Included:" not in output
