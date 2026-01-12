"""Tests for CLI output formatters.

Tests the unified formatter module that supports JSON, JSONL, Markdown, TOON, and CSV formats.
"""

from __future__ import annotations

import json

import pytest

from affinity.cli.formatters import (
    _detect_numeric_columns,
    _empty_output,
    _md_escape,
    _toon_quote,
    format_csv,
    format_data,
    format_json_data,
    format_jsonl,
    format_markdown,
    format_toon,
    to_cell,
)


class TestToCell:
    """Tests for to_cell() value conversion."""

    def test_to_cell_none(self) -> None:
        """Null values become empty string."""
        assert to_cell(None) == ""

    def test_to_cell_bool_true(self) -> None:
        """Boolean true becomes lowercase string."""
        assert to_cell(True) == "true"

    def test_to_cell_bool_false(self) -> None:
        """Boolean false becomes lowercase string."""
        assert to_cell(False) == "false"

    def test_to_cell_int(self) -> None:
        """Integer becomes string."""
        assert to_cell(42) == "42"

    def test_to_cell_float(self) -> None:
        """Float becomes string."""
        assert to_cell(3.14) == "3.14"

    def test_to_cell_string(self) -> None:
        """String passes through unchanged."""
        assert to_cell("hello") == "hello"

    def test_to_cell_list_simple(self) -> None:
        """List becomes semicolon-separated."""
        assert to_cell(["a", "b", "c"]) == "a; b; c"

    def test_to_cell_list_with_none(self) -> None:
        """List skips None values."""
        assert to_cell(["a", None, "b"]) == "a; b"

    def test_to_cell_dropdown_text_extraction(self) -> None:
        """Dropdown dict extracts text field."""
        assert to_cell({"id": "123", "text": "Active"}) == "Active"

    def test_to_cell_multiselect_text_extraction(self) -> None:
        """Multi-select list extracts text from each dict."""
        data = [
            {"id": "1", "text": "Tag A"},
            {"id": "2", "text": "Tag B"},
        ]
        assert to_cell(data) == "Tag A; Tag B"

    def test_to_cell_nested_dict_without_text(self) -> None:
        """Dict without text or known type becomes compact placeholder."""
        data = {"city": "NYC", "zip": "10001"}
        result = to_cell(data)
        # Now shows object count instead of JSON
        assert result == "object (2 keys)"

    def test_to_cell_mixed_list(self) -> None:
        """List with mixed types."""
        data = [1, "two", {"id": "3", "text": "Three"}]
        assert to_cell(data) == "1; two; Three"

    def test_to_cell_person_entity(self) -> None:
        """Person entity extracts name and id."""
        data = {"id": 123, "type": "person", "firstName": "John", "lastName": "Smith"}
        assert to_cell(data) == "John Smith (id=123)"

    def test_to_cell_person_entity_first_name_only(self) -> None:
        """Person entity with only first name."""
        data = {"id": 456, "type": "person", "firstName": "Jane"}
        assert to_cell(data) == "Jane (id=456)"

    def test_to_cell_person_entity_no_name(self) -> None:
        """Person entity without name shows type and id."""
        data = {"id": 789, "type": "person"}
        assert to_cell(data) == "person (id=789)"

    def test_to_cell_company_entity(self) -> None:
        """Company entity extracts name and id."""
        data = {"id": 100, "type": "company", "name": "Acme Corp", "domain": "acme.com"}
        assert to_cell(data) == "Acme Corp (id=100)"

    def test_to_cell_company_entity_domain_fallback(self) -> None:
        """Company entity falls back to domain if no name."""
        data = {"id": 200, "type": "company", "domain": "example.com"}
        assert to_cell(data) == "example.com (id=200)"

    def test_to_cell_company_entity_no_name(self) -> None:
        """Company entity without name shows type and id."""
        data = {"id": 300, "type": "company"}
        assert to_cell(data) == "company (id=300)"

    def test_to_cell_fields_container(self) -> None:
        """Fields container shows preview of field values."""
        data = {
            "data": {
                "field-1": {"name": "Status", "value": {"data": {"text": "Active"}}},
                "field-2": {
                    "name": "Owner",
                    "value": {"data": {"firstName": "Jane", "lastName": "Doe"}},
                },
            },
            "pagination": {"next_page_token": None},
        }
        result = to_cell(data)
        # Should show first 2 fields with preview
        assert "Status=Active" in result
        assert "Owner=Jane Doe" in result
        assert "(2 fields)" in result

    def test_to_cell_fields_container_single_field(self) -> None:
        """Fields container with single field."""
        data = {
            "data": {
                "field-1": {"name": "Priority", "value": {"data": "High"}},
            }
        }
        result = to_cell(data)
        assert "Priority=High" in result
        assert "(1 fields)" in result

    def test_to_cell_fields_container_empty(self) -> None:
        """Empty fields container."""
        data = {"data": {}}
        result = to_cell(data)
        # Empty data dict - no fields to show
        assert "object" in result or result == "object (1 keys)"

    def test_to_cell_flat_fields_dict(self) -> None:
        """Flat fields dict (query executor normalized format)."""
        data = {"Team Member": "LB", "Status": "Active"}
        result = to_cell(data)
        assert "Team Member=LB" in result
        assert "Status=Active" in result
        # No count suffix when all fields shown (<=2 fields)
        assert "fields)" not in result

    def test_to_cell_flat_fields_dict_single(self) -> None:
        """Flat fields dict with single field."""
        data = {"Status": "Active"}
        result = to_cell(data)
        assert result == "Status=Active"  # Clean output, no count

    def test_to_cell_flat_fields_dict_with_dropdown(self) -> None:
        """Flat fields dict with dropdown value."""
        data = {"Status": {"id": "123", "text": "In Progress"}}
        result = to_cell(data)
        assert "Status=In Progress" in result

    def test_to_cell_flat_fields_dict_with_list(self) -> None:
        """Flat fields dict with multi-select list value."""
        data = {"Team Member": ["LB", "JD"], "Status": "Active"}
        result = to_cell(data)
        assert "Team Member=LB; JD" in result
        # No count suffix when all fields shown (<=2 fields)
        assert "fields)" not in result

    def test_to_cell_flat_fields_dict_with_single_item_list(self) -> None:
        """Flat fields dict with single-item list (common for multi-select with one selection)."""
        data = {"Team Member": ["LB"]}
        result = to_cell(data)
        assert result == "Team Member=LB"  # Clean output, no count

    def test_to_cell_dict_with_name(self) -> None:
        """Generic dict with name field extracts the name."""
        data = {"name": "My List", "id": 42, "size": 100}
        assert to_cell(data) == "My List"

    def test_to_cell_list_export_format(self) -> None:
        """List export format with entityName and entityId."""
        data = {
            "listEntryId": 1,
            "entityType": "person",
            "entityId": 100,
            "entityName": "John Smith",
        }
        assert to_cell(data) == "John Smith (id=100)"

    def test_to_cell_dict_fallback(self) -> None:
        """Dict with simple values shows field preview."""
        data = {"foo": 1, "bar": 2, "baz": 3}
        result = to_cell(data)
        # Simple flat dicts get field preview
        assert "foo=1" in result
        assert "(3 fields)" in result

    def test_to_cell_dict_fallback_complex(self) -> None:
        """Dict with complex nested values shows key count."""
        data = {"nested": {"deeply": {"value": 1}}, "another": [1, 2, 3]}
        assert to_cell(data) == "object (2 keys)"


class TestFormatJsonData:
    """Tests for format_json_data()."""

    def test_format_json_data_basic(self) -> None:
        """Basic JSON array output."""
        data = [{"id": 1, "name": "Acme"}]
        result = format_json_data(data)
        assert json.loads(result) == data

    def test_format_json_data_empty(self) -> None:
        """Empty array."""
        result = format_json_data([])
        assert result == "[]"

    def test_format_json_data_pretty(self) -> None:
        """Pretty-printed JSON."""
        data = [{"id": 1}]
        result = format_json_data(data, pretty=True)
        assert "  " in result  # Has indentation


class TestFormatJsonl:
    """Tests for format_jsonl() JSON Lines output."""

    def test_format_jsonl_basic(self) -> None:
        """Basic JSONL output - one object per line."""
        data = [{"id": 1, "name": "Acme"}, {"id": 2, "name": "Beta"}]
        result = format_jsonl(data)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"id": 1, "name": "Acme"}
        assert json.loads(lines[1]) == {"id": 2, "name": "Beta"}

    def test_format_jsonl_empty(self) -> None:
        """Empty data produces empty string."""
        assert format_jsonl([]) == ""

    def test_format_jsonl_trailing_newline(self) -> None:
        """JSONL ends with newline per spec recommendation."""
        result = format_jsonl([{"id": 1}])
        assert result.endswith("\n")

    def test_format_jsonl_single_row(self) -> None:
        """Single row JSONL."""
        result = format_jsonl([{"a": 1}])
        assert result == '{"a": 1}\n'


class TestFormatMarkdown:
    """Tests for format_markdown() GitHub-flavored markdown tables."""

    def test_format_markdown_basic(self) -> None:
        """Basic markdown table."""
        data = [{"id": 1, "name": "Acme"}, {"id": 2, "name": "Beta"}]
        result = format_markdown(data, ["id", "name"])
        assert "| id | name |" in result
        # Note: id column is numeric so it gets right-aligned with ---:
        assert "| ---" in result
        assert "| 1 | Acme |" in result
        assert "| 2 | Beta |" in result

    def test_format_markdown_numeric_alignment(self) -> None:
        """Numeric columns get right-alignment."""
        data = [{"count": 42, "label": "test"}]
        result = format_markdown(data, ["count", "label"])
        # Numeric column should have ---: separator
        assert "---:" in result

    def test_format_markdown_pipe_escaping(self) -> None:
        """Pipe characters in values are escaped."""
        data = [{"note": "A | B"}]
        result = format_markdown(data, ["note"])
        assert "A \\| B" in result

    def test_format_markdown_newline_to_br(self) -> None:
        """Newlines become <br> in cells."""
        data = [{"note": "Line 1\nLine 2"}]
        result = format_markdown(data, ["note"])
        assert "Line 1<br>Line 2" in result

    def test_format_markdown_empty(self) -> None:
        """Empty data returns no results message."""
        assert format_markdown([], ["id"]) == "_No results_"


class TestFormatToon:
    """Tests for format_toon() Token-Optimized Object Notation."""

    def test_format_toon_basic(self) -> None:
        """Basic TOON output."""
        data = [{"id": 1, "name": "Acme"}, {"id": 2, "name": "Beta"}]
        result = format_toon(data, ["id", "name"])
        # Header with count and fields
        assert result.startswith("[2]{id,name}:")
        # Data rows indented
        assert "\n  1,Acme" in result
        assert "\n  2,Beta" in result

    def test_format_toon_quoting_rules(self) -> None:
        """Values requiring quotes are quoted."""
        data = [{"val": "has,comma"}, {"val": "has:colon"}, {"val": "plain"}]
        result = format_toon(data, ["val"])
        assert '"has,comma"' in result
        assert '"has:colon"' in result
        # Plain value should not be quoted
        lines = result.split("\n")
        assert any(line.strip() == "plain" for line in lines)

    def test_format_toon_empty(self) -> None:
        """Empty data with known fields."""
        result = format_toon([], ["id", "name"])
        assert result == "[0]{}:"

    def test_format_toon_reserved_words(self) -> None:
        """Reserved words (true, false, null) are quoted."""
        data = [{"val": "true"}, {"val": "false"}, {"val": "null"}]
        result = format_toon(data, ["val"])
        assert '"true"' in result
        assert '"false"' in result
        assert '"null"' in result

    def test_format_toon_numeric_pattern(self) -> None:
        """Numeric-looking strings are quoted."""
        data = [{"val": "123"}, {"val": "3.14"}, {"val": "-42"}]
        result = format_toon(data, ["val"])
        # All should be quoted since they look like numbers
        assert '"123"' in result
        assert '"3.14"' in result
        assert '"-42"' in result

    def test_format_toon_escape_sequences(self) -> None:
        """Special characters are escaped."""
        data = [{"val": 'has"quote'}, {"val": "has\\backslash"}]
        result = format_toon(data, ["val"])
        assert '\\"' in result  # Escaped quote
        assert "\\\\" in result  # Escaped backslash


class TestFormatCsv:
    """Tests for format_csv() CSV output."""

    def test_format_csv_basic(self) -> None:
        """Basic CSV output."""
        data = [{"id": 1, "name": "Acme"}, {"id": 2, "name": "Beta"}]
        result = format_csv(data, ["id", "name"])
        # CSV module may use \r\n on some systems, normalize line endings
        lines = [line.strip() for line in result.strip().split("\n")]
        assert lines[0] == "id,name"
        assert lines[1] == "1,Acme"
        assert lines[2] == "2,Beta"

    def test_format_csv_empty_with_fieldnames(self) -> None:
        """Empty data still has header row."""
        result = format_csv([], ["id", "name"])
        assert result.strip() == "id,name"

    def test_format_csv_quoting(self) -> None:
        """Values with commas are quoted."""
        data = [{"note": "A, B, C"}]
        result = format_csv(data, ["note"])
        assert '"A, B, C"' in result


class TestDetectNumericColumns:
    """Tests for _detect_numeric_columns()."""

    def test_detect_numeric_int(self) -> None:
        """Integer column detected."""
        data = [{"count": 1}, {"count": 2}]
        result = _detect_numeric_columns(data, ["count"])
        assert "count" in result

    def test_detect_numeric_float(self) -> None:
        """Float column detected."""
        data = [{"amount": 1.5}, {"amount": 2.5}]
        result = _detect_numeric_columns(data, ["amount"])
        assert "amount" in result

    def test_detect_numeric_mixed(self) -> None:
        """Mixed types column not detected as numeric."""
        data = [{"val": 1}, {"val": "two"}]
        result = _detect_numeric_columns(data, ["val"])
        assert "val" not in result

    def test_detect_numeric_with_nulls(self) -> None:
        """Column with nulls and numbers is numeric."""
        data = [{"count": 1}, {"count": None}, {"count": 3}]
        result = _detect_numeric_columns(data, ["count"])
        assert "count" in result


class TestEmptyOutput:
    """Tests for _empty_output() handling."""

    def test_empty_output_json(self) -> None:
        """JSON empty is empty array."""
        assert _empty_output("json") == "[]"

    def test_empty_output_jsonl(self) -> None:
        """JSONL empty is empty string."""
        assert _empty_output("jsonl") == ""

    def test_empty_output_markdown_with_fieldnames(self) -> None:
        """Markdown with fieldnames shows header-only table."""
        result = _empty_output("markdown", ["id", "name"])
        assert "| id | name |" in result
        assert "| --- | --- |" in result

    def test_empty_output_markdown_without_fieldnames(self) -> None:
        """Markdown without fieldnames shows no results."""
        assert _empty_output("markdown") == "_No results_"

    def test_empty_output_toon_with_fieldnames(self) -> None:
        """TOON with fieldnames shows zero-count header."""
        result = _empty_output("toon", ["id", "name"])
        assert result == "[0]{id,name}:"

    def test_empty_output_toon_without_fieldnames(self) -> None:
        """TOON without fieldnames shows minimal header."""
        assert _empty_output("toon") == "[0]{}:"

    def test_empty_output_csv_with_fieldnames(self) -> None:
        """CSV with fieldnames shows header."""
        result = _empty_output("csv", ["id", "name"])
        assert result == "id,name\n"

    def test_empty_output_csv_without_fieldnames(self) -> None:
        """CSV without fieldnames is empty."""
        assert _empty_output("csv") == ""


class TestToonQuote:
    """Tests for _toon_quote() quoting rules."""

    def test_toon_quote_empty_string(self) -> None:
        """Empty string must be quoted."""
        assert _toon_quote("") == '""'

    def test_toon_quote_whitespace(self) -> None:
        """Leading/trailing whitespace requires quotes."""
        assert _toon_quote(" hello") == '" hello"'
        assert _toon_quote("hello ") == '"hello "'

    def test_toon_quote_plain(self) -> None:
        """Plain string not quoted."""
        assert _toon_quote("hello") == "hello"

    def test_toon_quote_comma(self) -> None:
        """Comma requires quotes."""
        assert _toon_quote("a,b") == '"a,b"'

    def test_toon_quote_colon(self) -> None:
        """Colon requires quotes."""
        assert _toon_quote("a:b") == '"a:b"'

    def test_toon_quote_brackets(self) -> None:
        """Brackets require quotes."""
        assert _toon_quote("[a]") == '"[a]"'
        assert _toon_quote("{a}") == '"{a}"'


class TestMdEscape:
    """Tests for _md_escape() markdown escaping."""

    def test_md_escape_pipe(self) -> None:
        """Pipe escaped."""
        assert _md_escape("a | b") == "a \\| b"

    def test_md_escape_newline(self) -> None:
        """Newline becomes <br>."""
        assert _md_escape("a\nb") == "a<br>b"


class TestFormatData:
    """Tests for format_data() unified API."""

    def test_format_data_json(self) -> None:
        """JSON format."""
        data = [{"id": 1}]
        result = format_data(data, "json")
        assert json.loads(result) == data

    def test_format_data_jsonl(self) -> None:
        """JSONL format."""
        data = [{"id": 1}, {"id": 2}]
        result = format_data(data, "jsonl")
        assert result.count("\n") == 2  # One per row + trailing

    def test_format_data_markdown(self) -> None:
        """Markdown format."""
        data = [{"id": 1}]
        result = format_data(data, "markdown")
        assert "|" in result

    def test_format_data_toon(self) -> None:
        """TOON format."""
        data = [{"id": 1}]
        result = format_data(data, "toon")
        assert "[1]{" in result

    def test_format_data_csv(self) -> None:
        """CSV format."""
        data = [{"id": 1}]
        result = format_data(data, "csv")
        assert "id" in result

    def test_format_data_table_raises(self) -> None:
        """Table format raises error (use render.py instead)."""
        with pytest.raises(ValueError, match=r"Use render\.py"):
            format_data([{"id": 1}], "table")

    def test_format_data_empty(self) -> None:
        """Empty data uses _empty_output()."""
        assert format_data([], "json") == "[]"
        assert format_data([], "jsonl") == ""


class TestEdgeCases:
    """Edge case tests."""

    def test_unicode_characters(self) -> None:
        """Unicode characters preserved."""
        data = [{"name": "日本語"}, {"name": "émoji 🎉"}]
        for fmt in ("json", "jsonl", "markdown", "toon", "csv"):
            if fmt == "table":
                continue
            result = format_data(data, fmt)  # type: ignore[arg-type]
            assert "日本語" in result or "\\u" in result  # Either preserved or escaped
            # Emoji should be present (TOON and CSV preserve Unicode)

    def test_large_numeric_values(self) -> None:
        """Large numbers don't use scientific notation in TOON."""
        data = [{"amount": 123456789012345}]
        result = format_toon(data, ["amount"])
        # Should not contain 'e' or 'E' (scientific notation)
        assert "e" not in result.lower()
        assert "123456789012345" in result

    def test_dropdown_with_none_id(self) -> None:
        """Dropdown with None id but valid text."""
        data = [{"status": {"id": None, "text": "Pending"}}]
        result = to_cell(data[0]["status"])
        assert result == "Pending"

    def test_multiselect_with_mixed_values(self) -> None:
        """Multi-select with dict and scalar values."""
        data = [{"tags": [{"id": "1", "text": "A"}, "B", None]}]
        result = to_cell(data[0]["tags"])
        # Should extract A from dict, keep B, skip None
        assert "A" in result
        assert "B" in result
