"""Tests for query output field flattening.

Tests the field flattening functionality that shows explicitly-selected
nested structures (fields.*, interactionDates) in table/CSV/markdown output.

Related: docs/internal/query-fields-flatten-plan.md
"""

from __future__ import annotations

from affinity.cli.query.output import (
    _apply_explicit_flattening,
    _extract_display_value,
    _flatten_fields,
    _flatten_interaction_dates,
    _get_excluded_columns,
)


class TestExtractDisplayValue:
    """Tests for _extract_display_value function."""

    def test_passes_through_none(self) -> None:
        """None values pass through unchanged."""
        assert _extract_display_value(None) is None

    def test_passes_through_string(self) -> None:
        """String values pass through unchanged."""
        assert _extract_display_value("hello") == "hello"

    def test_passes_through_number(self) -> None:
        """Numeric values pass through unchanged."""
        assert _extract_display_value(42) == 42
        assert _extract_display_value(3.14) == 3.14

    def test_passes_through_boolean(self) -> None:
        """Boolean values pass through unchanged."""
        assert _extract_display_value(True) is True
        assert _extract_display_value(False) is False

    def test_joins_string_list(self) -> None:
        """List of strings is joined with comma."""
        assert _extract_display_value(["A", "B", "C"]) == "A, B, C"

    def test_joins_mixed_primitive_list(self) -> None:
        """List of mixed primitives is joined."""
        assert _extract_display_value(["A", 1, True]) == "A, 1, True"

    def test_extracts_location_from_dict(self) -> None:
        """Location dict is formatted as string."""
        location = {"city": "NYC", "state": "NY", "country": "USA"}
        assert _extract_display_value(location) == "NYC, NY, USA"

    def test_extracts_location_partial(self) -> None:
        """Location dict with missing parts formats correctly."""
        location = {"city": "London", "country": "UK"}
        assert _extract_display_value(location) == "London, UK"

    def test_extracts_location_city_only(self) -> None:
        """Location dict with only city."""
        location = {"city": "Tokyo"}
        assert _extract_display_value(location) == "Tokyo"

    def test_extracts_email_interaction_sent_at(self) -> None:
        """Email interaction extracts sentAt."""
        email = {"type": "email", "sentAt": "2026-01-15T10:00:00Z", "subject": "Hello"}
        assert _extract_display_value(email) == "2026-01-15T10:00:00Z"

    def test_extracts_meeting_interaction_start_time(self) -> None:
        """Meeting interaction extracts startTime."""
        meeting = {"type": "meeting", "startTime": "2026-01-15T14:00:00Z", "title": "Sync"}
        assert _extract_display_value(meeting) == "2026-01-15T14:00:00Z"

    def test_returns_generic_dict_as_is(self) -> None:
        """Generic dict without special keys returns as-is."""
        data = {"foo": "bar", "baz": 123}
        assert _extract_display_value(data) == {"foo": "bar", "baz": 123}


class TestFlattenFields:
    """Tests for _flatten_fields function."""

    def test_flatten_fields_simple(self) -> None:
        """Flatten simple fields dict to fields.X columns."""
        record = {"id": 1, "name": "Test", "fields": {"Status": "New", "Priority": "High"}}
        result = _flatten_fields(record)
        assert result == {
            "id": 1,
            "name": "Test",
            "fields.Status": "New",
            "fields.Priority": "High",
        }

    def test_flatten_fields_empty(self) -> None:
        """Empty fields dict produces no fields.* columns."""
        record = {"id": 1, "fields": {}}
        result = _flatten_fields(record)
        assert result == {"id": 1}
        assert "fields" not in result
        assert not any(k.startswith("fields.") for k in result)

    def test_flatten_fields_preserves_other_columns(self) -> None:
        """Non-fields columns pass through unchanged."""
        record = {
            "id": 1,
            "name": "Acme",
            "entityType": "company",
            "fields": {"Status": "Active"},
        }
        result = _flatten_fields(record)
        assert result["id"] == 1
        assert result["name"] == "Acme"
        assert result["entityType"] == "company"
        assert result["fields.Status"] == "Active"

    def test_flatten_fields_with_list_value(self) -> None:
        """List field values are joined with comma."""
        record = {"id": 1, "fields": {"Tags": ["VIP", "Priority", "New"]}}
        result = _flatten_fields(record)
        assert result["fields.Tags"] == "VIP, Priority, New"

    def test_flatten_fields_with_location(self) -> None:
        """Location field is formatted as string."""
        record = {
            "id": 1,
            "fields": {"Location": {"city": "San Francisco", "state": "CA", "country": "USA"}},
        }
        result = _flatten_fields(record)
        assert result["fields.Location"] == "San Francisco, CA, USA"

    def test_flatten_fields_without_fields_key(self) -> None:
        """Record without fields key passes through unchanged."""
        record = {"id": 1, "name": "Test"}
        result = _flatten_fields(record)
        assert result == {"id": 1, "name": "Test"}

    def test_flatten_fields_with_none_value(self) -> None:
        """Null field values are preserved."""
        record = {"id": 1, "fields": {"Status": None, "Priority": "High"}}
        result = _flatten_fields(record)
        assert result["fields.Status"] is None
        assert result["fields.Priority"] == "High"


class TestFlattenInteractionDates:
    """Tests for _flatten_interaction_dates function."""

    def test_flatten_interaction_dates_basic(self) -> None:
        """Flatten basic interaction dates."""
        record = {
            "id": 1,
            "interactionDates": {
                "lastEmail": {"date": "2026-01-10", "daysSince": 7},
                "lastMeeting": {"date": "2026-01-05", "daysSince": 12},
            },
        }
        result = _flatten_interaction_dates(record)
        assert result["id"] == 1
        assert result["lastEmail"] == "2026-01-10"
        assert result["lastEmailDaysSince"] == 7
        assert result["lastMeeting"] == "2026-01-05"
        assert result["lastMeetingDaysSince"] == 12
        assert "interactionDates" not in result

    def test_flatten_interaction_dates_with_days_until(self) -> None:
        """Flatten interaction dates with daysUntil (future events)."""
        record = {
            "id": 1,
            "interactionDates": {"nextMeeting": {"date": "2026-01-20", "daysUntil": 3}},
        }
        result = _flatten_interaction_dates(record)
        assert result["nextMeeting"] == "2026-01-20"
        assert result["nextMeetingDaysUntil"] == 3

    def test_flatten_interaction_dates_preserves_other_columns(self) -> None:
        """Other columns are preserved."""
        record = {
            "id": 1,
            "name": "Test",
            "interactionDates": {"lastEmail": {"date": "2026-01-10", "daysSince": 7}},
        }
        result = _flatten_interaction_dates(record)
        assert result["id"] == 1
        assert result["name"] == "Test"
        assert result["lastEmail"] == "2026-01-10"

    def test_flatten_interaction_dates_empty(self) -> None:
        """Empty interactionDates produces all canonical columns as null.

        Schema consistency requires all 8 columns even when no data is present,
        so TOON format can use consistent column headers across all records.
        """
        record = {"id": 1, "interactionDates": {}}
        result = _flatten_interaction_dates(record)
        assert result["id"] == 1
        # All canonical columns present with null values
        assert result["lastMeeting"] is None
        assert result["lastMeetingDaysSince"] is None
        assert result["nextMeeting"] is None
        assert result["nextMeetingDaysUntil"] is None
        assert result["lastEmail"] is None
        assert result["lastEmailDaysSince"] is None
        assert result["lastInteraction"] is None
        assert result["lastInteractionDaysSince"] is None
        assert "interactionDates" not in result

    def test_flatten_interaction_dates_null(self) -> None:
        """Null interaction date values are preserved."""
        record = {"id": 1, "interactionDates": {"lastEmail": None}}
        result = _flatten_interaction_dates(record)
        assert result["lastEmail"] is None
        # Other canonical columns also present
        assert result["lastMeeting"] is None
        assert result["nextMeeting"] is None
        assert result["lastInteraction"] is None


class TestFlattenInteractionDatesSchemaConsistency:
    """Tests for consistent schema across all interactionDates cases.

    TOON format uses the first record's keys as column headers, so all records
    must have identical keys to render correctly.
    """

    def test_null_produces_canonical_columns(self) -> None:
        """Null interactionDates produces all 8 canonical columns as null."""
        record = {"id": 1, "interactionDates": None}
        result = _flatten_interaction_dates(record)

        assert result["lastMeeting"] is None
        assert result["lastMeetingDaysSince"] is None
        assert result["nextMeeting"] is None
        assert result["nextMeetingDaysUntil"] is None
        assert result["lastEmail"] is None
        assert result["lastEmailDaysSince"] is None
        assert result["lastInteraction"] is None
        assert result["lastInteractionDaysSince"] is None
        assert "interactionDates" not in result

    def test_partial_data_produces_all_canonical_columns(self) -> None:
        """Partial interactionDates produces all 8 columns (data + nulls for missing)."""
        record = {
            "id": 1,
            "interactionDates": {"lastEmail": {"date": "2026-01-10", "daysSince": 7}},
        }
        result = _flatten_interaction_dates(record)

        # Has data
        assert result["lastEmail"] == "2026-01-10"
        assert result["lastEmailDaysSince"] == 7
        # Missing types have null columns (critical for schema consistency!)
        assert result["lastMeeting"] is None
        assert result["lastMeetingDaysSince"] is None
        assert result["nextMeeting"] is None
        assert result["nextMeetingDaysUntil"] is None
        assert result["lastInteraction"] is None
        assert result["lastInteractionDaysSince"] is None

    def test_mixed_records_have_identical_columns(self) -> None:
        """All records produce identical column sets (the core TOON requirement)."""
        data = [
            {"id": 1, "interactionDates": None},
            {"id": 2, "interactionDates": {}},
            {"id": 3, "interactionDates": {"lastEmail": {"date": "2026-01-10", "daysSince": 7}}},
            {
                "id": 4,
                "interactionDates": {
                    "lastMeeting": {"date": "2026-01-05", "daysSince": 12},
                    "nextMeeting": {"date": "2026-01-20", "daysUntil": 3},
                },
            },
        ]
        result = _apply_explicit_flattening(
            data, explicit_select=None, explicit_expand=["interactionDates"]
        )

        # All records should have identical keys
        keys = [set(r.keys()) for r in result]
        assert keys[0] == keys[1] == keys[2] == keys[3]

        # Verify expected columns present
        expected_interaction_cols = {
            "lastMeeting",
            "lastMeetingDaysSince",
            "nextMeeting",
            "nextMeetingDaysUntil",
            "lastEmail",
            "lastEmailDaysSince",
            "lastInteraction",
            "lastInteractionDaysSince",
        }
        for record_keys in keys:
            assert expected_interaction_cols.issubset(record_keys)


class TestApplyExplicitFlattening:
    """Tests for _apply_explicit_flattening function."""

    def test_no_flattening_without_explicit_select(self) -> None:
        """No flattening when fields not explicitly selected."""
        data = [{"id": 1, "fields": {"Status": "New"}}]
        result = _apply_explicit_flattening(data, explicit_select=None, explicit_expand=None)
        assert result == data  # Unchanged

    def test_flatten_with_fields_wildcard(self) -> None:
        """Flatten when fields.* is explicitly selected."""
        data = [{"id": 1, "fields": {"Status": "New", "Priority": "High"}}]
        result = _apply_explicit_flattening(
            data, explicit_select=["id", "fields.*"], explicit_expand=None
        )
        assert result[0]["fields.Status"] == "New"
        assert result[0]["fields.Priority"] == "High"
        assert "fields" not in result[0]

    def test_flatten_with_specific_field(self) -> None:
        """Flatten when specific fields.X is explicitly selected."""
        data = [{"id": 1, "fields": {"Status": "New", "Priority": "High"}}]
        result = _apply_explicit_flattening(
            data, explicit_select=["id", "fields.Status"], explicit_expand=None
        )
        assert result[0]["fields.Status"] == "New"
        assert result[0]["fields.Priority"] == "High"

    def test_flatten_with_interaction_dates_expand(self) -> None:
        """Flatten when interactionDates is explicitly expanded."""
        data = [
            {"id": 1, "interactionDates": {"lastEmail": {"date": "2026-01-10", "daysSince": 7}}}
        ]
        result = _apply_explicit_flattening(
            data, explicit_select=None, explicit_expand=["interactionDates"]
        )
        assert result[0]["lastEmail"] == "2026-01-10"
        assert result[0]["lastEmailDaysSince"] == 7
        assert "interactionDates" not in result[0]

    def test_flatten_both_fields_and_interaction_dates(self) -> None:
        """Flatten both fields and interactionDates."""
        data = [
            {
                "id": 1,
                "fields": {"Status": "New"},
                "interactionDates": {"lastEmail": {"date": "2026-01-10", "daysSince": 7}},
            }
        ]
        result = _apply_explicit_flattening(
            data, explicit_select=["fields.*"], explicit_expand=["interactionDates"]
        )
        assert result[0]["fields.Status"] == "New"
        assert result[0]["lastEmail"] == "2026-01-10"
        assert "fields" not in result[0]
        assert "interactionDates" not in result[0]

    def test_handles_empty_data(self) -> None:
        """Empty data returns empty list."""
        result = _apply_explicit_flattening([], explicit_select=["fields.*"], explicit_expand=None)
        assert result == []


class TestGetExcludedColumns:
    """Tests for _get_excluded_columns function."""

    def test_default_exclusions(self) -> None:
        """Default exclusions are returned when no explicit selections."""
        excluded = _get_excluded_columns(explicit_select=None, explicit_expand=None)
        assert "fields" in excluded
        assert "interaction_dates" in excluded

    def test_fields_not_excluded_when_explicitly_selected(self) -> None:
        """fields is not excluded when fields.* is selected."""
        excluded = _get_excluded_columns(explicit_select=["fields.*"], explicit_expand=None)
        assert "fields" not in excluded
        # Other exclusions remain
        assert "interaction_dates" in excluded

    def test_interaction_dates_not_excluded_when_expanded(self) -> None:
        """interaction_dates not excluded when interactionDates expanded."""
        excluded = _get_excluded_columns(explicit_select=None, explicit_expand=["interactionDates"])
        assert "interaction_dates" not in excluded
        assert "interactionDates" not in excluded
        # Other exclusions remain
        assert "fields" in excluded

    def test_both_not_excluded(self) -> None:
        """Both fields and interaction_dates can be not excluded."""
        excluded = _get_excluded_columns(
            explicit_select=["fields.*"], explicit_expand=["interactionDates"]
        )
        assert "fields" not in excluded
        assert "interaction_dates" not in excluded
        assert "interactionDates" not in excluded

    def test_specific_field_triggers_exclusion_removal(self) -> None:
        """Specific field path like fields.Status also triggers exclusion removal."""
        excluded = _get_excluded_columns(explicit_select=["fields.Status"], explicit_expand=None)
        assert "fields" not in excluded


# =============================================================================
# Integration Tests: End-to-End Format Output
# =============================================================================


class TestTableFormatWithFlattening:
    """Integration tests for table format with field flattening."""

    def test_table_shows_flattened_fields_with_explicit_select(self) -> None:
        """Table output shows flattened fields.X columns when explicitly selected."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_table

        result = QueryResult(
            data=[
                {"id": 1, "name": "Acme", "fields": {"Status": "Active", "Owner": "Jane Doe"}},
                {"id": 2, "name": "TechCo", "fields": {"Status": "New", "Owner": "John Smith"}},
            ],
            explicit_select=["id", "name", "fields.*"],
            explicit_expand=None,
        )

        output = format_table(result)

        # Should show flattened field columns
        assert "fields.Status" in output
        assert "fields.Owner" in output
        assert "Active" in output
        assert "Jane Doe" in output

    def test_table_hides_fields_without_explicit_select(self) -> None:
        """Table output hides fields column when not explicitly selected (default behavior)."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_table

        result = QueryResult(
            data=[
                {"id": 1, "name": "Acme", "fields": {"Status": "Active"}},
            ],
            explicit_select=None,  # No explicit select
            explicit_expand=None,
        )

        output = format_table(result)

        # Should NOT show fields columns (default exclusion)
        assert "fields.Status" not in output
        assert "Status" not in output or "fields" not in output

    def test_table_shows_interaction_dates_with_expand(self) -> None:
        """Table output shows interaction date columns when expanded."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_table

        result = QueryResult(
            data=[
                {
                    "id": 1,
                    "name": "Acme",
                    "interactionDates": {
                        "lastEmail": {"date": "2026-01-10", "daysSince": 7},
                        "lastMeeting": {"date": "2026-01-05", "daysSince": 12},
                    },
                },
            ],
            explicit_select=None,
            explicit_expand=["interactionDates"],
        )

        output = format_table(result)

        # With 8 canonical columns + id + name = 10 columns, table truncates some.
        # Verify that interaction columns appear (headers may be truncated).
        assert "lastMee" in output  # lastMeeting column (truncated header)
        assert "2026-01" in output  # Date values present (may be truncated)
        assert "12" in output  # lastMeetingDaysSince value (short, not truncated)


class TestJsonFormatWithExplicitSelect:
    """Integration tests for JSON format behavior with explicit selections."""

    def test_json_keeps_nested_fields_structure(self) -> None:
        """JSON output keeps nested fields structure (never flattens)."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_json

        result = QueryResult(
            data=[
                {"id": 1, "name": "Acme", "fields": {"Status": "Active", "Owner": "Jane Doe"}},
            ],
            explicit_select=["id", "name", "fields.*"],  # Even with explicit select
            explicit_expand=None,
        )

        output = format_json(result, pretty=True)

        import json

        parsed = json.loads(output)

        # JSON should preserve nested structure
        assert "data" in parsed
        assert parsed["data"][0]["fields"] == {"Status": "Active", "Owner": "Jane Doe"}
        # Should NOT have flattened keys in JSON
        assert "fields.Status" not in parsed["data"][0]
        assert "fields.Owner" not in parsed["data"][0]

    def test_json_keeps_nested_interaction_dates(self) -> None:
        """JSON output keeps nested interactionDates structure."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_json

        result = QueryResult(
            data=[
                {
                    "id": 1,
                    "interactionDates": {"lastEmail": {"date": "2026-01-10", "daysSince": 7}},
                },
            ],
            explicit_select=None,
            explicit_expand=["interactionDates"],  # Even with explicit expand
        )

        output = format_json(result)

        import json

        parsed = json.loads(output)

        # JSON should preserve nested structure
        assert parsed["data"][0]["interactionDates"]["lastEmail"]["date"] == "2026-01-10"
        # Should NOT have flattened keys
        assert "lastEmail" not in parsed["data"][0] or isinstance(
            parsed["data"][0].get("lastEmail"), dict
        )


class TestCsvMarkdownFormatWithFlattening:
    """Integration tests for CSV and Markdown formats with flattening."""

    def test_csv_flattens_fields_with_explicit_select(self) -> None:
        """CSV output flattens fields when explicitly selected."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_query_result

        result = QueryResult(
            data=[
                {"id": 1, "name": "Acme", "fields": {"Status": "Active"}},
            ],
            explicit_select=["id", "name", "fields.Status"],
            explicit_expand=None,
        )

        output = format_query_result(result, "csv")

        # CSV should have flattened field header
        assert "fields.Status" in output
        assert "Active" in output

    def test_markdown_flattens_fields_with_explicit_select(self) -> None:
        """Markdown output flattens fields when explicitly selected."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_query_result

        result = QueryResult(
            data=[
                {"id": 1, "name": "Acme", "fields": {"Status": "Active", "Priority": "High"}},
            ],
            explicit_select=["id", "fields.*"],
            explicit_expand=None,
        )

        output = format_query_result(result, "markdown")

        # Markdown table should have flattened field columns
        assert "fields.Status" in output
        assert "fields.Priority" in output
        assert "Active" in output
        assert "High" in output


class TestPersonCompanyNormalizationFormats:
    """Integration tests for person/company field normalization in output formats.

    These tests verify the bug fix from BUG-person-company-field-normalization.md.
    """

    def test_normalized_person_field_in_table(self) -> None:
        """Person reference fields show as names in table output."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_table

        # After normalization, person fields are strings (not dicts)
        result = QueryResult(
            data=[
                {"id": 1, "name": "Acme", "fields": {"Owner": "Jane Doe", "Status": "Active"}},
            ],
            explicit_select=["id", "name", "fields.*"],
            explicit_expand=None,
        )

        output = format_table(result)

        # Person name should display correctly (not "object (3 keys)")
        assert "Jane Doe" in output
        assert "object" not in output.lower() or "object" not in output

    def test_normalized_person_field_in_json(self) -> None:
        """Person reference fields are strings in JSON output (after normalization)."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_json

        # After normalization, person fields are strings
        result = QueryResult(
            data=[
                {"id": 1, "fields": {"Owner": "Jane Doe", "Team": ["Alice Smith", "Bob Jones"]}},
            ],
        )

        output = format_json(result)

        import json

        parsed = json.loads(output)

        # Person fields should be strings (not objects)
        assert parsed["data"][0]["fields"]["Owner"] == "Jane Doe"
        assert parsed["data"][0]["fields"]["Team"] == ["Alice Smith", "Bob Jones"]

    def test_normalized_company_field_in_table(self) -> None:
        """Company reference fields show as names in table output."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_table

        # After normalization, company fields are strings
        result = QueryResult(
            data=[
                {"id": 1, "name": "Deal 1", "fields": {"Account": "Acme Corp"}},
            ],
            explicit_select=["id", "name", "fields.*"],
            explicit_expand=None,
        )

        output = format_table(result)

        # Company name should display correctly
        assert "Acme Corp" in output

    def test_normalized_multi_select_person_field(self) -> None:
        """Multi-select person fields show as comma-separated names."""
        from affinity.cli.query.models import QueryResult
        from affinity.cli.query.output import format_table

        # After normalization, multi-select person fields are lists of strings
        result = QueryResult(
            data=[
                {
                    "id": 1,
                    "name": "Project",
                    "fields": {"Team Members": ["Jane Doe", "John Smith"]},
                },
            ],
            explicit_select=["id", "name", "fields.*"],
            explicit_expand=None,
        )

        output = format_table(result)

        # Should show comma-separated names
        assert "Jane Doe" in output
        assert "John Smith" in output
