"""Tests for query filter operators."""

from __future__ import annotations

import pytest

from affinity.cli.query import compile_filter, matches, resolve_field_path
from affinity.cli.query.models import WhereClause


class TestResolveFieldPath:
    """Tests for resolve_field_path function."""

    def test_simple_field(self) -> None:
        """Resolve simple field path."""
        record = {"name": "Alice", "age": 30}
        assert resolve_field_path(record, "name") == "Alice"
        assert resolve_field_path(record, "age") == 30

    def test_nested_field(self) -> None:
        """Resolve nested field path."""
        record = {"address": {"city": "NYC", "zip": "10001"}}
        assert resolve_field_path(record, "address.city") == "NYC"

    def test_array_index(self) -> None:
        """Resolve array index."""
        record = {"emails": ["a@test.com", "b@test.com"]}
        assert resolve_field_path(record, "emails[0]") == "a@test.com"
        assert resolve_field_path(record, "emails[1]") == "b@test.com"

    def test_missing_field(self) -> None:
        """Return None for missing field."""
        record = {"name": "Alice"}
        assert resolve_field_path(record, "missing") is None

    def test_deeply_nested(self) -> None:
        """Resolve deeply nested path."""
        record = {"a": {"b": {"c": {"d": "value"}}}}
        assert resolve_field_path(record, "a.b.c.d") == "value"

    def test_array_out_of_bounds(self) -> None:
        """Return None for out of bounds array index."""
        record = {"items": ["a", "b"]}
        assert resolve_field_path(record, "items[10]") is None

    def test_fields_prefix(self) -> None:
        """Resolve fields.* for list entry fields."""
        record = {"fields": {"Status": "Active", "Priority": "High"}}
        assert resolve_field_path(record, "fields.Status") == "Active"


class TestFilterOperators:
    """Tests for individual filter operators."""

    @pytest.mark.req("QUERY-FILT-001")
    def test_eq_operator(self) -> None:
        """Test eq operator."""
        where = WhereClause(path="name", op="eq", value="Alice")
        assert matches({"name": "Alice"}, where)
        assert not matches({"name": "Bob"}, where)

    @pytest.mark.req("QUERY-FILT-001")
    def test_neq_operator(self) -> None:
        """Test neq operator."""
        where = WhereClause(path="name", op="neq", value="Alice")
        assert not matches({"name": "Alice"}, where)
        assert matches({"name": "Bob"}, where)

    @pytest.mark.req("QUERY-FILT-001")
    def test_eq_with_none(self) -> None:
        """Test eq with None values."""
        where = WhereClause(path="name", op="eq", value=None)
        assert matches({"name": None}, where)
        assert not matches({"name": "Alice"}, where)

    def test_gt_operator(self) -> None:
        """Test gt operator."""
        where = WhereClause(path="age", op="gt", value=30)
        assert matches({"age": 35}, where)
        assert not matches({"age": 30}, where)
        assert not matches({"age": 25}, where)

    def test_gte_operator(self) -> None:
        """Test gte operator."""
        where = WhereClause(path="age", op="gte", value=30)
        assert matches({"age": 35}, where)
        assert matches({"age": 30}, where)
        assert not matches({"age": 25}, where)

    def test_lt_operator(self) -> None:
        """Test lt operator."""
        where = WhereClause(path="age", op="lt", value=30)
        assert not matches({"age": 35}, where)
        assert not matches({"age": 30}, where)
        assert matches({"age": 25}, where)

    def test_lte_operator(self) -> None:
        """Test lte operator."""
        where = WhereClause(path="age", op="lte", value=30)
        assert not matches({"age": 35}, where)
        assert matches({"age": 30}, where)
        assert matches({"age": 25}, where)

    @pytest.mark.req("QUERY-FILT-002")
    def test_contains_operator(self) -> None:
        """Test contains operator (case insensitive)."""
        where = WhereClause(path="email", op="contains", value="acme")
        assert matches({"email": "alice@acme.com"}, where)
        assert matches({"email": "bob@ACME.COM"}, where)
        assert not matches({"email": "bob@test.com"}, where)

    @pytest.mark.req("QUERY-FILT-002")
    def test_starts_with_operator(self) -> None:
        """Test starts_with operator."""
        where = WhereClause(path="name", op="starts_with", value="al")
        assert matches({"name": "Alice"}, where)
        assert matches({"name": "albert"}, where)
        assert not matches({"name": "Bob"}, where)

    @pytest.mark.req("QUERY-FILT-003")
    def test_in_operator(self) -> None:
        """Test in operator."""
        where = WhereClause(path="status", op="in", value=["active", "pending"])
        assert matches({"status": "active"}, where)
        assert matches({"status": "pending"}, where)
        assert not matches({"status": "closed"}, where)

    @pytest.mark.req("QUERY-FILT-003")
    def test_between_operator(self) -> None:
        """Test between operator (inclusive)."""
        where = WhereClause(path="age", op="between", value=[20, 30])
        assert matches({"age": 20}, where)
        assert matches({"age": 25}, where)
        assert matches({"age": 30}, where)
        assert not matches({"age": 19}, where)
        assert not matches({"age": 31}, where)

    @pytest.mark.req("QUERY-FILT-004")
    def test_is_null_operator(self) -> None:
        """Test is_null operator."""
        where = WhereClause(path="email", op="is_null", value=None)
        assert matches({"email": None}, where)
        assert matches({"name": "Alice"}, where)  # Missing field = None
        assert not matches({"email": "test@test.com"}, where)

    @pytest.mark.req("QUERY-FILT-004")
    def test_is_not_null_operator(self) -> None:
        """Test is_not_null operator."""
        where = WhereClause(path="email", op="is_not_null", value=None)
        assert not matches({"email": None}, where)
        assert matches({"email": "test@test.com"}, where)

    @pytest.mark.req("QUERY-FILT-005")
    def test_contains_any_operator(self) -> None:
        """Test contains_any operator."""
        where = WhereClause(path="bio", op="contains_any", value=["python", "java"])
        assert matches({"bio": "I love Python programming"}, where)
        assert matches({"bio": "Java developer here"}, where)
        assert not matches({"bio": "Go is my favorite language"}, where)

    @pytest.mark.req("QUERY-FILT-005")
    def test_contains_all_operator(self) -> None:
        """Test contains_all operator."""
        where = WhereClause(path="bio", op="contains_all", value=["python", "developer"])
        assert matches({"bio": "Python developer at Acme"}, where)
        assert not matches({"bio": "Python programmer"}, where)


class TestCompoundFilters:
    """Tests for compound filter expressions."""

    @pytest.mark.req("QUERY-FILT-006")
    def test_and_condition(self) -> None:
        """Test AND compound condition."""
        where = WhereClause(
            and_=[
                WhereClause(path="age", op="gte", value=18),
                WhereClause(path="age", op="lte", value=65),
            ]
        )
        assert matches({"age": 30}, where)
        assert not matches({"age": 10}, where)
        assert not matches({"age": 70}, where)

    @pytest.mark.req("QUERY-FILT-006")
    def test_or_condition(self) -> None:
        """Test OR compound condition."""
        where = WhereClause(
            or_=[
                WhereClause(path="status", op="eq", value="active"),
                WhereClause(path="status", op="eq", value="pending"),
            ]
        )
        assert matches({"status": "active"}, where)
        assert matches({"status": "pending"}, where)
        assert not matches({"status": "closed"}, where)

    @pytest.mark.req("QUERY-FILT-006")
    def test_not_condition(self) -> None:
        """Test NOT condition."""
        where = WhereClause(not_=WhereClause(path="status", op="eq", value="deleted"))
        assert matches({"status": "active"}, where)
        assert not matches({"status": "deleted"}, where)

    def test_nested_compound(self) -> None:
        """Test nested compound conditions."""
        where = WhereClause(
            or_=[
                WhereClause(
                    and_=[
                        WhereClause(path="age", op="gte", value=18),
                        WhereClause(path="verified", op="eq", value=True),
                    ]
                ),
                WhereClause(path="role", op="eq", value="admin"),
            ]
        )
        # Adult verified user
        assert matches({"age": 30, "verified": True}, where)
        # Admin regardless of age
        assert matches({"age": 10, "role": "admin"}, where)
        # Unverified adult non-admin
        assert not matches({"age": 30, "verified": False}, where)


class TestCompileFilter:
    """Tests for compile_filter function."""

    def test_compile_and_execute(self) -> None:
        """Compile and execute a filter function."""
        where = WhereClause(path="name", op="eq", value="Alice")
        filter_fn = compile_filter(where)

        records = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35},
        ]

        filtered = [r for r in records if filter_fn(r)]
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Alice"

    def test_compile_no_conditions(self) -> None:
        """Filter with no conditions matches all."""
        where = WhereClause()
        filter_fn = compile_filter(where)

        records = [{"a": 1}, {"b": 2}]
        assert all(filter_fn(r) for r in records)

    def test_matches_with_none_where(self) -> None:
        """matches() with None where matches all."""
        assert matches({"any": "record"}, None)


# =============================================================================
# Edge Case Tests for Filter Operators
# =============================================================================


class TestFilterOperatorEdgeCases:
    """Edge case tests for individual filter operators."""

    def test_neq_with_none_field(self) -> None:
        """Test neq with None field value."""
        where = WhereClause(path="name", op="neq", value="Alice")
        # None != "Alice" should be True
        assert matches({"name": None}, where)

    def test_neq_with_none_value(self) -> None:
        """Test neq when comparing to None value."""
        where = WhereClause(path="name", op="neq", value=None)
        # "Alice" != None should be True
        assert matches({"name": "Alice"}, where)
        # None != None should be False
        assert not matches({"name": None}, where)

    def test_gt_with_none_field(self) -> None:
        """Greater than with None field returns False."""
        where = WhereClause(path="age", op="gt", value=30)
        assert not matches({"age": None}, where)

    def test_gt_with_none_value(self) -> None:
        """Greater than with None value returns False."""
        where = WhereClause(path="age", op="gt", value=None)
        assert not matches({"age": 35}, where)

    def test_comparison_numeric_coercion(self) -> None:
        """Comparison operators coerce strings to numbers when possible.

        This is important for CRM data where filter values are often strings
        but field values are numeric. The compare module tries numeric
        coercion first before falling back to string comparison.
        """
        # Comparing int field to string filter value - numeric coercion
        where = WhereClause(path="value", op="gt", value="50")
        # 100 > 50 numerically = True (not lexicographic string comparison)
        assert matches({"value": 100}, where)

    def test_in_with_non_list_value(self) -> None:
        """in operator with non-list value returns False."""
        where = WhereClause(path="status", op="in", value="active")  # not a list
        assert not matches({"status": "active"}, where)

    def test_in_with_none_field(self) -> None:
        """in operator with None field returns False."""
        where = WhereClause(path="status", op="in", value=["active", "pending"])
        assert not matches({"status": None}, where)

    def test_between_invalid_list_length(self) -> None:
        """between operator with wrong list length returns False."""
        where = WhereClause(path="age", op="between", value=[20])  # Only one value
        assert not matches({"age": 25}, where)

    def test_between_not_a_list(self) -> None:
        """between operator with non-list returns False."""
        where = WhereClause(path="age", op="between", value=25)
        assert not matches({"age": 25}, where)

    def test_between_with_none_field(self) -> None:
        """between operator with None field returns False."""
        where = WhereClause(path="age", op="between", value=[20, 30])
        assert not matches({"age": None}, where)

    def test_between_type_error(self) -> None:
        """between operator with incomparable types returns False."""
        where = WhereClause(path="value", op="between", value=["a", "z"])
        # Can't compare int to string range
        assert not matches({"value": 25}, where)

    def test_contains_with_none_field(self) -> None:
        """contains operator with None field returns False."""
        where = WhereClause(path="bio", op="contains", value="test")
        assert not matches({"bio": None}, where)

    def test_contains_with_none_value(self) -> None:
        """contains operator with None value returns False."""
        where = WhereClause(path="bio", op="contains", value=None)
        assert not matches({"bio": "some text"}, where)

    def test_starts_with_with_none(self) -> None:
        """starts_with operator with None returns False."""
        where = WhereClause(path="name", op="starts_with", value="A")
        assert not matches({"name": None}, where)

        where2 = WhereClause(path="name", op="starts_with", value=None)
        assert not matches({"name": "Alice"}, where2)

    def test_contains_any_with_none_field(self) -> None:
        """contains_any with None field returns False."""
        where = WhereClause(path="bio", op="contains_any", value=["python", "java"])
        assert not matches({"bio": None}, where)

    def test_contains_any_with_non_list(self) -> None:
        """contains_any with non-list value returns False."""
        where = WhereClause(path="bio", op="contains_any", value="python")
        assert not matches({"bio": "I love Python"}, where)

    def test_contains_all_with_none_field(self) -> None:
        """contains_all with None field returns False."""
        where = WhereClause(path="bio", op="contains_all", value=["python", "developer"])
        assert not matches({"bio": None}, where)

    def test_contains_all_with_non_list(self) -> None:
        """contains_all with non-list value returns False."""
        where = WhereClause(path="bio", op="contains_all", value="python")
        assert not matches({"bio": "Python developer"}, where)


# =============================================================================
# Edge Case Tests for Field Path Resolution
# =============================================================================


class TestFieldPathEdgeCases:
    """Edge case tests for resolve_field_path and _parse_field_path."""

    def test_empty_path(self) -> None:
        """Empty path returns None."""
        record = {"name": "Alice"}
        assert resolve_field_path(record, "") is None

    def test_intermediate_none(self) -> None:
        """Returns None when intermediate value is None."""
        record = {"address": None}
        assert resolve_field_path(record, "address.city") is None

    def test_intermediate_not_dict(self) -> None:
        """Returns None when intermediate value is not a dict."""
        record = {"address": "123 Main St"}  # String, not dict
        assert resolve_field_path(record, "address.city") is None

    def test_array_negative_index(self) -> None:
        """Negative array index returns None."""
        record = {"items": ["a", "b", "c"]}
        assert resolve_field_path(record, "items[-1]") is None

    def test_array_on_non_list(self) -> None:
        """Array access on non-list returns None."""
        record = {"items": "not a list"}
        assert resolve_field_path(record, "items[0]") is None

    def test_non_numeric_array_index(self) -> None:
        """Non-numeric array index is treated as dict key."""
        record = {"items": {"foo": "bar"}}
        # [foo] should be treated as dict key access
        assert resolve_field_path(record, "items[foo]") == "bar"

    def test_unclosed_bracket_error(self) -> None:
        """Unclosed bracket raises QueryValidationError."""
        from affinity.cli.query import QueryValidationError

        record = {"items": ["a", "b"]}
        with pytest.raises(QueryValidationError, match="Unclosed bracket"):
            resolve_field_path(record, "items[0")

    def test_complex_path_with_arrays_and_nesting(self) -> None:
        """Complex path with multiple arrays and nested objects."""
        record = {
            "users": [
                {"name": "Alice", "addresses": [{"city": "NYC"}, {"city": "LA"}]},
                {"name": "Bob", "addresses": [{"city": "SF"}]},
            ]
        }
        assert resolve_field_path(record, "users[0].addresses[1].city") == "LA"
        assert resolve_field_path(record, "users[1].addresses[0].city") == "SF"


# =============================================================================
# Edge Case Tests for compile_filter
# =============================================================================


class TestCompileFilterEdgeCases:
    """Edge case tests for compile_filter function."""

    def test_unknown_operator_raises(self) -> None:
        """Unknown operator raises QueryValidationError."""
        from affinity.cli.query import QueryValidationError

        where = WhereClause(path="name", op="unknown_op", value="Alice")
        with pytest.raises(QueryValidationError, match="Unknown operator"):
            compile_filter(where)

    def test_all_quantifier_raises_not_implemented(self) -> None:
        """all_ quantifier in compile_filter() raises NotImplementedError.

        Note: Quantifiers ARE implemented via compile_filter_with_context().
        The basic compile_filter() doesn't support them because they require
        pre-fetched relationship data. See TestCompileFilterWithContext for
        tests of the full implementation.
        """
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            all_=QuantifierClause(
                path="tags", where=WhereClause(path="value", op="eq", value="vip")
            )
        )
        with pytest.raises(NotImplementedError, match=r"all_.*requires relationship data"):
            compile_filter(where)

    def test_none_quantifier_raises_not_implemented(self) -> None:
        """none_ quantifier in compile_filter() raises NotImplementedError.

        See test_all_quantifier_raises_not_implemented for design rationale.
        """
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            none_=QuantifierClause(
                path="tags", where=WhereClause(path="value", op="eq", value="spam")
            )
        )
        with pytest.raises(NotImplementedError, match=r"none_.*requires relationship data"):
            compile_filter(where)

    def test_exists_raises_not_implemented(self) -> None:
        """exists_ in compile_filter() raises NotImplementedError.

        See test_all_quantifier_raises_not_implemented for design rationale.
        """
        from affinity.cli.query.models import ExistsClause

        where = WhereClause(
            # Use alias 'from' for the from_ field
            exists_=ExistsClause(**{"from": "related", "via": "personId"})
        )
        with pytest.raises(NotImplementedError, match=r"exists_.*requires relationship data"):
            compile_filter(where)

    def test_count_pseudo_field_raises_not_implemented(self) -> None:
        """_count pseudo-field in compile_filter() raises NotImplementedError.

        See test_all_quantifier_raises_not_implemented for design rationale.
        """
        where = WhereClause(path="companies._count", op="gt", value=5)
        with pytest.raises(NotImplementedError, match=r"_count.*requires relationship data"):
            compile_filter(where)

    def test_condition_with_no_op_matches_all(self) -> None:
        """Condition with None op matches all."""
        # This tests _compile_condition when op is None
        where = WhereClause(path="name")  # op is None
        filter_fn = compile_filter(where)
        assert filter_fn({"name": "Alice"}) is True
        assert filter_fn({"name": "Bob"}) is True

    def test_condition_with_none_path_matches_all(self) -> None:
        """Condition with None path matches all."""
        where = WhereClause(op="eq", value="Alice")  # path is None
        filter_fn = compile_filter(where)
        assert filter_fn({"name": "Alice"}) is True


# =============================================================================
# Edge Case Tests for Date Parsing in Filters
# =============================================================================


class TestDateParsingInFilters:
    """Tests for date parsing integration in filters."""

    def test_relative_date_in_filter(self) -> None:
        """Relative date values are parsed in filters."""
        import datetime

        from affinity.cli.query.dates import parse_date_value

        # This tests the parse_date_value integration
        # "today" is parsed into a timezone-aware datetime object
        where = WhereClause(path="createdAt", op="gte", value="today")
        filter_fn = compile_filter(where)

        # Get the parsed "today" value to know the timezone
        today_parsed = parse_date_value("today")
        assert today_parsed is not None

        # Create timezone-aware datetimes matching the parser's output
        tomorrow = today_parsed + datetime.timedelta(days=1)
        yesterday = today_parsed - datetime.timedelta(days=1)

        # Today or later should match gte today
        assert filter_fn({"createdAt": today_parsed}) is True
        assert filter_fn({"createdAt": tomorrow}) is True
        # Yesterday should not match gte today
        assert filter_fn({"createdAt": yesterday}) is False

    def test_non_date_string_passthrough(self) -> None:
        """Non-date strings pass through unchanged."""
        where = WhereClause(path="status", op="eq", value="active")
        filter_fn = compile_filter(where)
        assert filter_fn({"status": "active"}) is True


# =============================================================================
# Array Field Filtering Tests (Multi-select dropdown support)
# =============================================================================


class TestArrayFieldFiltering:
    """Test filtering on multi-select/array fields."""

    @pytest.mark.req("QUERY-FILT-007")
    def test_eq_on_array_field_checks_membership(self) -> None:
        """eq operator should check if value is IN the array."""
        record = {"fields": {"Team Member": ["LB", "MA", "RK"]}}
        where = WhereClause(path="fields.Team Member", op="eq", value="LB")
        assert matches(record, where) is True

    @pytest.mark.req("QUERY-FILT-007")
    def test_eq_on_array_field_no_match(self) -> None:
        """eq returns False when value not in array."""
        record = {"fields": {"Team Member": ["MA", "RK"]}}
        where = WhereClause(path="fields.Team Member", op="eq", value="LB")
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-007")
    def test_eq_list_to_list_set_equality(self) -> None:
        """eq with list value checks set equality (order-insensitive)."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(path="fields.Team Member", op="eq", value=["LB", "MA"])
        assert matches(record, where) is True

        # Order doesn't matter - set equality
        where2 = WhereClause(path="fields.Team Member", op="eq", value=["MA", "LB"])
        assert matches(record, where2) is True

        # Different elements - not equal
        where3 = WhereClause(path="fields.Team Member", op="eq", value=["LB", "RK"])
        assert matches(record, where3) is False

    @pytest.mark.req("QUERY-FILT-007")
    def test_neq_on_array_field_value_absent(self) -> None:
        """neq returns True when value is NOT in array."""
        record = {"fields": {"Team Member": ["MA", "RK"]}}
        where = WhereClause(path="fields.Team Member", op="neq", value="LB")
        assert matches(record, where) is True

    @pytest.mark.req("QUERY-FILT-007")
    def test_neq_on_array_field_value_present(self) -> None:
        """neq returns False when value IS in array."""
        record = {"fields": {"Team Member": ["LB", "MA", "RK"]}}
        where = WhereClause(path="fields.Team Member", op="neq", value="LB")
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-007")
    def test_in_with_array_field(self) -> None:
        """in operator with array field checks any intersection."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(path="fields.Team Member", op="in", value=["LB", "DW"])
        assert matches(record, where) is True

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_all(self) -> None:
        """has_all requires all specified values present."""
        record = {"fields": {"Team Member": ["LB", "MA", "RK"]}}
        where = WhereClause(path="fields.Team Member", op="has_all", value=["LB", "MA"])
        assert matches(record, where) is True

        where2 = WhereClause(path="fields.Team Member", op="has_all", value=["LB", "DW"])
        assert matches(record, where2) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_any(self) -> None:
        """has_any requires any specified value present."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(path="fields.Team Member", op="has_any", value=["LB", "DW"])
        assert matches(record, where) is True

        where2 = WhereClause(path="fields.Team Member", op="has_any", value=["XX", "YY"])
        assert matches(record, where2) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_any_with_empty_array_field(self) -> None:
        """Empty array field should not match any value."""
        record = {"fields": {"Team Member": []}}
        where = WhereClause(path="fields.Team Member", op="has_any", value=["LB"])
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_all_with_empty_array_field(self) -> None:
        """Empty array field should not match any value."""
        record = {"fields": {"Team Member": []}}
        where = WhereClause(path="fields.Team Member", op="has_all", value=["LB"])
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_any_with_non_list_field(self) -> None:
        """has_any returns False when field is not a list."""
        record = {"fields": {"Status": "New"}}
        where = WhereClause(path="fields.Status", op="has_any", value=["New"])
        assert matches(record, where) is False  # Status is scalar, not list

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_all_with_non_list_value(self) -> None:
        """has_all requires list value."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(path="fields.Team Member", op="has_all", value="LB")  # scalar
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_any_with_empty_filter_list(self) -> None:
        """has_any with empty filter list returns False."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(path="fields.Team Member", op="has_any", value=[])
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_all_with_empty_filter_list(self) -> None:
        """has_all with empty filter list returns False (not vacuous true)."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(path="fields.Team Member", op="has_all", value=[])
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-007")
    def test_eq_on_single_value_field_unchanged(self) -> None:
        """eq on non-array fields should work as before."""
        record = {"fields": {"Status": "New"}}
        where = WhereClause(path="fields.Status", op="eq", value="New")
        assert matches(record, where) is True

    @pytest.mark.req("QUERY-FILT-007")
    def test_empty_array_field(self) -> None:
        """Empty array should not match any value."""
        record = {"fields": {"Team Member": []}}
        where = WhereClause(path="fields.Team Member", op="eq", value="LB")
        assert matches(record, where) is False

    # --- Additional edge cases ---

    @pytest.mark.req("QUERY-FILT-007")
    def test_single_element_array(self) -> None:
        """Single-element array should match its element."""
        record = {"fields": {"Team Member": ["LB"]}}
        where = WhereClause(path="fields.Team Member", op="eq", value="LB")
        assert matches(record, where) is True

        # Single-element array vs single-element list
        where2 = WhereClause(path="fields.Team Member", op="eq", value=["LB"])
        assert matches(record, where2) is True  # Exact match

    @pytest.mark.req("QUERY-FILT-007")
    def test_null_in_array(self) -> None:
        """Arrays containing None should handle null comparisons."""
        record = {"fields": {"Team Member": [None, "LB"]}}
        where = WhereClause(path="fields.Team Member", op="eq", value="LB")
        assert matches(record, where) is True

        where2 = WhereClause(path="fields.Team Member", op="eq", value=None)
        assert matches(record, where2) is True  # None is in the array

    @pytest.mark.req("QUERY-FILT-007")
    def test_empty_string_in_array(self) -> None:
        """Arrays containing empty string should match empty string."""
        record = {"fields": {"Team Member": ["", "LB"]}}
        where = WhereClause(path="fields.Team Member", op="eq", value="")
        assert matches(record, where) is True

        where2 = WhereClause(path="fields.Team Member", op="eq", value="LB")
        assert matches(record, where2) is True

    @pytest.mark.req("QUERY-FILT-007")
    def test_in_with_empty_array_field(self) -> None:
        """in operator with empty array field returns False."""
        record = {"fields": {"Team Member": []}}
        where = WhereClause(path="fields.Team Member", op="in", value=["LB", "MA"])
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-007")
    def test_neq_list_to_list_set_equality(self) -> None:
        """neq with list value checks set inequality."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        # Same sets (different order) - should be False (not not-equal)
        where = WhereClause(path="fields.Team Member", op="neq", value=["MA", "LB"])
        assert matches(record, where) is False

        # Different sets - should be True (they are not-equal)
        where2 = WhereClause(path="fields.Team Member", op="neq", value=["LB", "RK"])
        assert matches(record, where2) is True

    # --- Compound filters with multi-select fields ---

    @pytest.mark.req("QUERY-FILT-007")
    def test_and_with_array_fields(self) -> None:
        """AND compound condition with array fields."""
        record = {"fields": {"Team Member": ["LB", "MA"], "Status": "Active"}}
        where = WhereClause(
            and_=[
                WhereClause(path="fields.Team Member", op="eq", value="LB"),
                WhereClause(path="fields.Status", op="eq", value="Active"),
            ]
        )
        assert matches(record, where) is True

        # Fails when one condition doesn't match
        where2 = WhereClause(
            and_=[
                WhereClause(path="fields.Team Member", op="eq", value="XX"),
                WhereClause(path="fields.Status", op="eq", value="Active"),
            ]
        )
        assert matches(record, where2) is False

    @pytest.mark.req("QUERY-FILT-007")
    def test_or_with_array_fields(self) -> None:
        """OR compound condition with array fields."""
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(
            or_=[
                WhereClause(path="fields.Team Member", op="eq", value="LB"),
                WhereClause(path="fields.Team Member", op="eq", value="XX"),
            ]
        )
        assert matches(record, where) is True

        # Both conditions fail
        where2 = WhereClause(
            or_=[
                WhereClause(path="fields.Team Member", op="eq", value="XX"),
                WhereClause(path="fields.Team Member", op="eq", value="YY"),
            ]
        )
        assert matches(record, where2) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_compound_with_has_any_has_all(self) -> None:
        """Compound filters using has_any and has_all operators."""
        record = {"fields": {"Team Member": ["LB", "MA", "RK"]}}
        # has_all AND has_any
        where = WhereClause(
            and_=[
                WhereClause(path="fields.Team Member", op="has_all", value=["LB", "MA"]),
                WhereClause(path="fields.Team Member", op="has_any", value=["RK", "XX"]),
            ]
        )
        assert matches(record, where) is True

    # --- Type mismatch edge cases ---

    @pytest.mark.req("QUERY-FILT-007")
    def test_eq_array_with_int_value(self) -> None:
        """eq on array field with integer value."""
        record = {"fields": {"IDs": [1, 2, 3]}}
        where = WhereClause(path="fields.IDs", op="eq", value=2)
        assert matches(record, where) is True

        where2 = WhereClause(path="fields.IDs", op="eq", value=99)
        assert matches(record, where2) is False

    @pytest.mark.req("QUERY-FILT-007")
    def test_eq_mixed_type_array(self) -> None:
        """eq on array with mixed types."""
        record = {"fields": {"Mixed": ["a", 1, None]}}
        where = WhereClause(path="fields.Mixed", op="eq", value="a")
        assert matches(record, where) is True

        where2 = WhereClause(path="fields.Mixed", op="eq", value=1)
        assert matches(record, where2) is True

    @pytest.mark.req("QUERY-FILT-007")
    def test_in_with_type_mismatch(self) -> None:
        """in operator with type mismatch between array and filter list."""
        # String array, integer in filter list - no match expected
        record = {"fields": {"Team Member": ["LB", "MA"]}}
        where = WhereClause(path="fields.Team Member", op="in", value=[1, 2, 3])
        assert matches(record, where) is False

    @pytest.mark.req("QUERY-FILT-008")
    def test_has_any_with_mixed_types(self) -> None:
        """has_any with mixed type values."""
        record = {"fields": {"Values": [1, "two", 3.0]}}
        where = WhereClause(path="fields.Values", op="has_any", value=["two", 99])
        assert matches(record, where) is True

        where2 = WhereClause(path="fields.Values", op="has_any", value=[1, 99])
        assert matches(record, where2) is True


# =============================================================================
# Enhanced Filter Context Tests (Quantifiers, Exists, _count)
# =============================================================================


class TestRequiresRelationshipData:
    """Tests for requires_relationship_data() detection function."""

    def test_detects_all_quantifier(self) -> None:
        """Detects all_ quantifier requires relationship data."""
        from affinity.cli.query.filters import requires_relationship_data
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            all_=QuantifierClause(
                path="companies",
                where=WhereClause(path="name", op="contains", value="Inc"),
            )
        )
        required = requires_relationship_data(where)
        assert "companies" in required

    def test_detects_none_quantifier(self) -> None:
        """Detects none_ quantifier requires relationship data."""
        from affinity.cli.query.filters import requires_relationship_data
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            none_=QuantifierClause(
                path="interactions",
                where=WhereClause(path="type", op="eq", value="spam"),
            )
        )
        required = requires_relationship_data(where)
        assert "interactions" in required

    def test_detects_exists_clause(self) -> None:
        """Detects exists_ clause requires relationship data."""
        from affinity.cli.query.filters import requires_relationship_data
        from affinity.cli.query.models import ExistsClause

        where = WhereClause(exists_=ExistsClause(**{"from": "interactions"}))
        required = requires_relationship_data(where)
        assert "interactions" in required

    def test_detects_count_pseudo_field(self) -> None:
        """Detects _count pseudo-field requires relationship data."""
        from affinity.cli.query.filters import requires_relationship_data

        where = WhereClause(path="companies._count", op="gte", value=2)
        required = requires_relationship_data(where)
        assert "companies" in required

    def test_detects_nested_in_and_clause(self) -> None:
        """Detects quantifiers nested in AND clause."""
        from affinity.cli.query.filters import requires_relationship_data
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            and_=[
                WhereClause(path="name", op="eq", value="Alice"),
                WhereClause(
                    all_=QuantifierClause(
                        path="companies",
                        where=WhereClause(path="name", op="contains", value="Inc"),
                    )
                ),
            ]
        )
        required = requires_relationship_data(where)
        assert "companies" in required

    def test_returns_empty_for_simple_filter(self) -> None:
        """Returns empty set for simple filter without quantifiers."""
        from affinity.cli.query.filters import requires_relationship_data

        where = WhereClause(path="name", op="eq", value="Alice")
        required = requires_relationship_data(where)
        assert required == set()

    def test_returns_empty_for_none(self) -> None:
        """Returns empty set for None where clause."""
        from affinity.cli.query.filters import requires_relationship_data

        required = requires_relationship_data(None)
        assert required == set()

    def test_invalid_count_path_raises_error(self) -> None:
        """Malformed _count path raises QueryValidationError."""
        from affinity.cli.query.exceptions import QueryValidationError
        from affinity.cli.query.filters import requires_relationship_data

        # Path is "._count" with no relationship
        where = WhereClause(path="._count", op="gte", value=2)
        with pytest.raises(QueryValidationError, match="Invalid _count path"):
            requires_relationship_data(where)

    def test_nested_count_path_raises_error(self) -> None:
        """Nested _count path raises QueryValidationError."""
        from affinity.cli.query.exceptions import QueryValidationError
        from affinity.cli.query.filters import requires_relationship_data

        # Nested path like "companies.tags._count" is not supported
        where = WhereClause(path="companies.tags._count", op="gte", value=2)
        with pytest.raises(QueryValidationError, match="Nested _count paths not supported"):
            requires_relationship_data(where)


class TestCheckNoNestedQuantifiers:
    """Tests for _check_no_nested_quantifiers() validation."""

    def test_allows_simple_where(self) -> None:
        """Allows simple WHERE clause without quantifiers."""
        from affinity.cli.query.filters import _check_no_nested_quantifiers

        where = WhereClause(path="name", op="eq", value="Test")
        # Should not raise
        _check_no_nested_quantifiers(where, "test context")

    def test_rejects_nested_all(self) -> None:
        """Rejects nested all_ quantifier."""
        from affinity.cli.query.exceptions import QueryValidationError
        from affinity.cli.query.filters import _check_no_nested_quantifiers
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            all_=QuantifierClause(
                path="nested",
                where=WhereClause(path="x", op="eq", value=1),
            )
        )
        with pytest.raises(QueryValidationError, match="Nested quantifiers not supported"):
            _check_no_nested_quantifiers(where, "outer quantifier")

    def test_rejects_nested_none(self) -> None:
        """Rejects nested none_ quantifier."""
        from affinity.cli.query.exceptions import QueryValidationError
        from affinity.cli.query.filters import _check_no_nested_quantifiers
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            none_=QuantifierClause(
                path="nested",
                where=WhereClause(path="x", op="eq", value=1),
            )
        )
        with pytest.raises(QueryValidationError, match="Nested quantifiers not supported"):
            _check_no_nested_quantifiers(where, "outer quantifier")

    def test_rejects_nested_exists(self) -> None:
        """Rejects nested exists_ clause."""
        from affinity.cli.query.exceptions import QueryValidationError
        from affinity.cli.query.filters import _check_no_nested_quantifiers
        from affinity.cli.query.models import ExistsClause

        where = WhereClause(exists_=ExistsClause(**{"from": "nested"}))
        with pytest.raises(QueryValidationError, match="Nested quantifiers not supported"):
            _check_no_nested_quantifiers(where, "outer quantifier")

    def test_rejects_quantifier_in_compound(self) -> None:
        """Rejects quantifiers nested in compound clauses."""
        from affinity.cli.query.exceptions import QueryValidationError
        from affinity.cli.query.filters import _check_no_nested_quantifiers
        from affinity.cli.query.models import QuantifierClause

        where = WhereClause(
            and_=[
                WhereClause(path="x", op="eq", value=1),
                WhereClause(
                    all_=QuantifierClause(
                        path="nested",
                        where=WhereClause(path="y", op="eq", value=2),
                    )
                ),
            ]
        )
        with pytest.raises(QueryValidationError, match="Nested quantifiers not supported"):
            _check_no_nested_quantifiers(where, "outer quantifier")


class TestCompileFilterWithContext:
    """Tests for compile_filter_with_context() enhanced filter compiler."""

    def test_all_quantifier_all_match(self) -> None:
        """all_ quantifier returns True when all related items match."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import QuantifierClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {1: [{"name": "Acme Inc"}, {"name": "Tech Inc"}]}},
            relationship_counts={"companies": {1: 2}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            all_=QuantifierClause(
                path="companies",
                where=WhereClause(path="name", op="contains", value="Inc"),
            )
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True

    def test_all_quantifier_some_dont_match(self) -> None:
        """all_ quantifier returns False when some related items don't match."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import QuantifierClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {1: [{"name": "Acme Inc"}, {"name": "Good Corp"}]}},
            relationship_counts={"companies": {1: 2}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            all_=QuantifierClause(
                path="companies",
                where=WhereClause(path="name", op="contains", value="Inc"),
            )
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is False  # "Good Corp" doesn't contain "Inc"

    def test_all_quantifier_vacuous_truth(self) -> None:
        """all_ quantifier returns True for empty relationship (vacuous truth)."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import QuantifierClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {}},  # No companies for any record
            relationship_counts={"companies": {}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            all_=QuantifierClause(
                path="companies",
                where=WhereClause(path="name", op="contains", value="Inc"),
            )
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True  # Vacuous truth

    def test_none_quantifier_none_match(self) -> None:
        """none_ quantifier returns True when no related items match."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import QuantifierClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {1: [{"name": "Acme Inc"}, {"name": "Good Corp"}]}},
            relationship_counts={"companies": {1: 2}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            none_=QuantifierClause(
                path="companies",
                where=WhereClause(path="name", op="contains", value="Spam"),
            )
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True  # No company contains "Spam"

    def test_none_quantifier_some_match(self) -> None:
        """none_ quantifier returns False when some related items match."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import QuantifierClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {1: [{"name": "Acme Inc"}, {"name": "Spam Corp"}]}},
            relationship_counts={"companies": {1: 2}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            none_=QuantifierClause(
                path="companies",
                where=WhereClause(path="name", op="contains", value="Spam"),
            )
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is False  # "Spam Corp" contains "Spam"

    def test_exists_with_items(self) -> None:
        """exists_ returns True when related items exist."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import ExistsClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"interactions": {1: [{"type": "email"}]}},
            relationship_counts={"interactions": {1: 1}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(exists_=ExistsClause(**{"from": "interactions"}))
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True

    def test_exists_without_items(self) -> None:
        """exists_ returns False when no related items exist."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import ExistsClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"interactions": {}},
            relationship_counts={"interactions": {}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(exists_=ExistsClause(**{"from": "interactions"}))
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is False

    def test_exists_with_filter(self) -> None:
        """exists_ with where clause filters related items."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import ExistsClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"interactions": {1: [{"type": "email"}, {"type": "meeting"}]}},
            relationship_counts={"interactions": {1: 2}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            exists_=ExistsClause(
                **{
                    "from": "interactions",
                    "where": {"path": "type", "op": "eq", "value": "email"},
                }
            )
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True

    def test_exists_with_filter_no_match(self) -> None:
        """exists_ with where clause returns False when no items match filter."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.models import ExistsClause
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"interactions": {1: [{"type": "email"}]}},
            relationship_counts={"interactions": {1: 1}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            exists_=ExistsClause(
                **{
                    "from": "interactions",
                    "where": {"path": "type", "op": "eq", "value": "call"},
                }
            )
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is False  # No "call" type interactions

    def test_count_gte(self) -> None:
        """_count with gte operator works correctly."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {1: [{}, {}]}},
            relationship_counts={"companies": {1: 2}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(path="companies._count", op="gte", value=2)
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True

    def test_count_lt(self) -> None:
        """_count with lt operator works correctly."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {1: [{}]}},
            relationship_counts={"companies": {1: 1}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(path="companies._count", op="lt", value=2)
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True

    def test_count_eq_zero(self) -> None:
        """_count with eq 0 works for records with no relationships."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {}},  # No data means 0 companies
            relationship_counts={"companies": {}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(path="companies._count", op="eq", value=0)
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1}) is True  # Default count is 0

    def test_count_non_numeric_value_raises_error(self) -> None:
        """_count with non-numeric value raises QueryValidationError."""
        from affinity.cli.query.exceptions import QueryValidationError
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={},
            relationship_counts={},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(path="companies._count", op="gte", value="two")
        with pytest.raises(QueryValidationError, match="numeric value"):
            compile_filter_with_context(where, ctx)

    def test_compound_and_clause(self) -> None:
        """Compound AND clause with quantifier works correctly."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={"companies": {1: [{}, {}]}},
            relationship_counts={"companies": {1: 2}},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(
            and_=[
                WhereClause(path="name", op="eq", value="Alice"),
                WhereClause(path="companies._count", op="gte", value=1),
            ]
        )
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"id": 1, "name": "Alice"}) is True
        assert filter_fn({"id": 1, "name": "Bob"}) is False

    def test_simple_condition_delegates_to_compile_filter(self) -> None:
        """Simple conditions delegate to existing compile_filter."""
        from affinity.cli.query.filters import FilterContext, compile_filter_with_context
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        schema = SCHEMA_REGISTRY["persons"]
        ctx = FilterContext(
            relationship_data={},
            relationship_counts={},
            schema=schema,
            id_field="id",
        )
        where = WhereClause(path="name", op="eq", value="Alice")
        filter_fn = compile_filter_with_context(where, ctx)
        assert filter_fn({"name": "Alice"}) is True
        assert filter_fn({"name": "Bob"}) is False


class TestFindRelationshipByTarget:
    """Tests for find_relationship_by_target() schema helper."""

    def test_finds_matching_relationship(self) -> None:
        """Finds relationship by target entity type."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY, find_relationship_by_target

        schema = SCHEMA_REGISTRY["persons"]
        rel_name = find_relationship_by_target(schema, "interactions")
        assert rel_name == "interactions"

    def test_finds_companies_relationship(self) -> None:
        """Finds companies relationship on persons schema."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY, find_relationship_by_target

        schema = SCHEMA_REGISTRY["persons"]
        rel_name = find_relationship_by_target(schema, "companies")
        assert rel_name == "companies"

    def test_returns_none_for_unknown_entity(self) -> None:
        """Returns None for unknown target entity."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY, find_relationship_by_target

        schema = SCHEMA_REGISTRY["persons"]
        rel_name = find_relationship_by_target(schema, "unknown_entity")
        assert rel_name is None

    def test_returns_none_for_empty_relationships(self) -> None:
        """Returns None for schema with no relationships."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY, find_relationship_by_target

        schema = SCHEMA_REGISTRY["notes"]  # notes has no relationships
        rel_name = find_relationship_by_target(schema, "anything")
        assert rel_name is None
