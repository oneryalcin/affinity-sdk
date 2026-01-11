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
