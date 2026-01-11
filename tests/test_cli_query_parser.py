"""Tests for the query parser."""

from __future__ import annotations

import pytest

from affinity.cli.query import (
    QueryParseError,
    QueryValidationError,
    parse_query,
    parse_query_from_file,
)


class TestParseQuery:
    """Tests for parse_query function."""

    @pytest.mark.req("QUERY-PARSE-001")
    def test_parse_simple_from_and_limit(self) -> None:
        """Parse simple query with from and limit."""
        result = parse_query({"from": "persons", "limit": 10})
        assert result.query.from_ == "persons"
        assert result.query.limit == 10

    @pytest.mark.req("QUERY-PARSE-001")
    def test_parse_with_version(self) -> None:
        """Parse query with explicit version."""
        result = parse_query({"$version": "1.0", "from": "companies", "limit": 5})
        assert result.query.version == "1.0"
        assert result.query.from_ == "companies"
        assert len(result.warnings) == 0

    @pytest.mark.req("QUERY-PARSE-001")
    def test_parse_warns_on_missing_version(self) -> None:
        """Warn when $version is missing."""
        result = parse_query({"from": "persons"})
        assert len(result.warnings) == 1
        assert "$version" in result.warnings[0]

    @pytest.mark.req("QUERY-PARSE-002")
    def test_parse_compound_where_and(self) -> None:
        """Parse compound WHERE with AND."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "and": [
                        {"path": "email", "op": "contains", "value": "@acme.com"},
                        {"path": "firstName", "op": "eq", "value": "John"},
                    ]
                },
            }
        )
        assert result.query.where is not None
        assert result.query.where.and_ is not None
        assert len(result.query.where.and_) == 2

    @pytest.mark.req("QUERY-PARSE-002")
    def test_parse_compound_where_or(self) -> None:
        """Parse compound WHERE with OR."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "or": [
                        {"path": "email", "op": "contains", "value": "@acme.com"},
                        {"path": "email", "op": "contains", "value": "@example.com"},
                    ]
                },
            }
        )
        assert result.query.where is not None
        assert result.query.where.or_ is not None
        assert len(result.query.where.or_) == 2

    @pytest.mark.req("QUERY-PARSE-003")
    def test_reject_invalid_operator(self) -> None:
        """Reject unknown operators."""
        with pytest.raises(QueryParseError) as exc:
            parse_query(
                {
                    "from": "persons",
                    "where": {"path": "name", "op": "like", "value": "%test%"},
                }
            )
        assert "like" in str(exc.value)

    @pytest.mark.req("QUERY-PARSE-003")
    def test_reject_unsupported_version(self) -> None:
        """Reject unsupported query version."""
        with pytest.raises(QueryParseError) as exc:
            parse_query({"$version": "99.0", "from": "persons"})
        assert "99.0" in str(exc.value)
        assert "Unsupported" in str(exc.value)

    @pytest.mark.req("QUERY-PARSE-004")
    def test_reject_aggregate_with_include(self) -> None:
        """Reject aggregate combined with include."""
        with pytest.raises(QueryValidationError) as exc:
            parse_query(
                {
                    "from": "persons",
                    "include": ["companies"],
                    "aggregate": {"total": {"count": True}},
                }
            )
        assert "aggregate" in str(exc.value).lower()

    @pytest.mark.req("QUERY-PARSE-005")
    def test_parse_quantifier_all(self) -> None:
        """Parse quantifier 'all'."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "all": {
                        "path": "interactions",
                        "where": {"path": "type", "op": "eq", "value": "MEETING"},
                    }
                },
            }
        )
        assert result.query.where is not None
        assert result.query.where.all_ is not None
        assert result.query.where.all_.path == "interactions"

    @pytest.mark.req("QUERY-PARSE-005")
    def test_parse_quantifier_none(self) -> None:
        """Parse quantifier 'none'."""
        result = parse_query(
            {
                "from": "companies",
                "where": {
                    "none": {
                        "path": "people",
                        "where": {"path": "role", "op": "eq", "value": "CEO"},
                    }
                },
            }
        )
        assert result.query.where is not None
        assert result.query.where.none_ is not None

    @pytest.mark.req("QUERY-PARSE-006")
    def test_parse_exists_subquery(self) -> None:
        """Parse EXISTS subquery."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "exists": {
                        "from": "interactions",
                        "via": "personId",
                        "where": {"path": "type", "op": "eq", "value": "MEETING"},
                    }
                },
            }
        )
        assert result.query.where is not None
        assert result.query.where.exists_ is not None
        assert result.query.where.exists_.from_ == "interactions"

    @pytest.mark.req("QUERY-PARSE-007")
    def test_parse_count_pseudo_field(self) -> None:
        """Parse _count pseudo-field in WHERE."""
        result = parse_query(
            {
                "from": "persons",
                "where": {"path": "companies._count", "op": "gte", "value": 2},
            }
        )
        assert result.query.where is not None
        assert result.query.where.path == "companies._count"

    def test_parse_all_operators(self) -> None:
        """Ensure all supported operators parse correctly."""
        operators = [
            ("eq", "test"),
            ("neq", "test"),
            ("gt", 10),
            ("gte", 10),
            ("lt", 10),
            ("lte", 10),
            ("contains", "test"),
            ("starts_with", "test"),
            ("in", ["a", "b"]),
            ("between", [1, 10]),
            ("is_null", None),
            ("is_not_null", None),
            ("contains_any", ["a", "b"]),
            ("contains_all", ["a", "b"]),
        ]
        for op, value in operators:
            result = parse_query(
                {
                    "from": "persons",
                    "where": {"path": "field", "op": op, "value": value},
                }
            )
            assert result.query.where is not None
            assert result.query.where.op == op

    def test_parse_between_requires_two_elements(self) -> None:
        """Between operator requires exactly two elements."""
        with pytest.raises(QueryValidationError) as exc:
            parse_query(
                {
                    "from": "persons",
                    "where": {"path": "age", "op": "between", "value": [1, 2, 3]},
                }
            )
        assert "between" in str(exc.value).lower()

    def test_parse_in_requires_array(self) -> None:
        """In operator requires array value."""
        with pytest.raises(QueryValidationError) as exc:
            parse_query(
                {
                    "from": "persons",
                    "where": {"path": "status", "op": "in", "value": "single_value"},
                }
            )
        assert "in" in str(exc.value).lower()

    def test_reject_unknown_entity(self) -> None:
        """Reject unknown entity types."""
        with pytest.raises(QueryValidationError) as exc:
            parse_query({"from": "unknownEntity"})
        assert "unknownEntity" in str(exc.value)

    def test_parse_with_order_by(self) -> None:
        """Parse query with orderBy."""
        result = parse_query(
            {
                "from": "persons",
                "orderBy": [
                    {"field": "lastName", "direction": "asc"},
                    {"field": "firstName", "direction": "desc"},
                ],
            }
        )
        assert result.query.order_by is not None
        assert len(result.query.order_by) == 2
        assert result.query.order_by[0].field == "lastName"
        assert result.query.order_by[0].direction == "asc"

    def test_parse_with_select(self) -> None:
        """Parse query with select fields."""
        result = parse_query(
            {
                "from": "persons",
                "select": ["firstName", "lastName", "email"],
            }
        )
        assert result.query.select is not None
        assert len(result.query.select) == 3

    def test_parse_with_include(self) -> None:
        """Parse query with includes."""
        result = parse_query(
            {
                "from": "persons",
                "include": ["companies", "opportunities"],
            }
        )
        assert result.query.include is not None
        assert len(result.query.include) == 2

    def test_parse_aggregate_count(self) -> None:
        """Parse aggregate with count."""
        result = parse_query(
            {
                "from": "persons",
                "aggregate": {"total": {"count": True}},
            }
        )
        assert result.query.aggregate is not None
        assert "total" in result.query.aggregate

    def test_parse_aggregate_sum(self) -> None:
        """Parse aggregate with sum."""
        result = parse_query(
            {
                "from": "opportunities",
                "aggregate": {"totalAmount": {"sum": "amount"}},
            }
        )
        assert result.query.aggregate is not None
        assert "totalAmount" in result.query.aggregate

    def test_parse_group_by(self) -> None:
        """Parse query with groupBy."""
        result = parse_query(
            {
                "from": "persons",
                "groupBy": "company",
                "aggregate": {"count": {"count": True}},
            }
        )
        assert result.query.group_by == "company"

    def test_reject_group_by_without_aggregate(self) -> None:
        """Reject groupBy without aggregate."""
        with pytest.raises(QueryValidationError) as exc:
            parse_query(
                {
                    "from": "persons",
                    "groupBy": "company",
                }
            )
        assert "groupBy" in str(exc.value)

    def test_reject_having_without_aggregate(self) -> None:
        """Reject having without aggregate."""
        with pytest.raises(QueryValidationError) as exc:
            parse_query(
                {
                    "from": "persons",
                    "having": {"path": "count", "op": "gt", "value": 5},
                }
            )
        assert "having" in str(exc.value)

    def test_parse_from_json_string(self) -> None:
        """Parse query from JSON string."""
        result = parse_query('{"from": "persons", "limit": 5}')
        assert result.query.from_ == "persons"
        assert result.query.limit == 5

    def test_reject_invalid_json(self) -> None:
        """Reject invalid JSON string."""
        with pytest.raises(QueryParseError) as exc:
            parse_query('{"from": "persons", limit: 5}')  # Missing quotes around limit
        assert "Invalid JSON" in str(exc.value)

    def test_parse_version_override(self) -> None:
        """Version override takes precedence."""
        result = parse_query(
            {"$version": "1.0", "from": "persons"},
            version_override="1.0",  # Same version, but explicitly overridden
        )
        assert result.query.version == "1.0"

    def test_parse_not_condition(self) -> None:
        """Parse NOT condition."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "not": {"path": "email", "op": "is_null"},
                },
            }
        )
        assert result.query.where is not None
        assert result.query.where.not_ is not None

    def test_warns_on_zero_limit(self) -> None:
        """Warn when limit is 0."""
        result = parse_query({"from": "persons", "limit": 0})
        assert any("limit=0" in w for w in result.warnings)

    def test_listentries_requires_listid_or_listname_error(self) -> None:
        """Error for listEntries without required filter shows both options."""
        with pytest.raises(QueryParseError) as exc:
            parse_query({"from": "listEntries"})

        error_msg = str(exc.value)
        # Error should mention both listId and listName as alternatives
        assert "listId" in error_msg
        assert "listName" in error_msg
        # Should show example for both
        assert "By ID:" in error_msg or "By name:" in error_msg


class TestParseQueryFromFile:
    """Tests for parse_query_from_file function."""

    def test_parse_from_file(self, tmp_path) -> None:
        """Parse query from a file."""
        query_file = tmp_path / "query.json"
        query_file.write_text('{"from": "persons", "limit": 10}')

        result = parse_query_from_file(str(query_file))
        assert result.query.from_ == "persons"
        assert result.query.limit == 10

    def test_parse_from_nonexistent_file(self, tmp_path) -> None:
        """Error on nonexistent file."""
        with pytest.raises(QueryParseError) as exc:
            parse_query_from_file(str(tmp_path / "nonexistent.json"))
        assert "Failed to read" in str(exc.value)
