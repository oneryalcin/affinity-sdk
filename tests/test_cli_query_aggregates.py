"""Tests for query aggregate functions."""

from __future__ import annotations

import pytest

from affinity.cli.query import apply_having, compute_aggregates, group_and_aggregate
from affinity.cli.query.models import AggregateFunc, HavingClause


class TestComputeAggregates:
    """Tests for compute_aggregates function."""

    @pytest.fixture
    def records(self) -> list[dict]:
        """Sample records for testing."""
        return [
            {"name": "Alice", "amount": 100, "category": "A"},
            {"name": "Bob", "amount": 200, "category": "B"},
            {"name": "Charlie", "amount": 150, "category": "A"},
            {"name": "Diana", "amount": 300, "category": "B"},
        ]

    @pytest.mark.req("QUERY-AGG-001")
    def test_sum_aggregate(self, records: list[dict]) -> None:
        """Compute sum of a field."""
        aggs = {"total": AggregateFunc(sum="amount")}
        result = compute_aggregates(records, aggs)
        assert result["total"] == 750  # 100 + 200 + 150 + 300

    @pytest.mark.req("QUERY-AGG-001")
    def test_avg_aggregate(self, records: list[dict]) -> None:
        """Compute average of a field."""
        aggs = {"average": AggregateFunc(avg="amount")}
        result = compute_aggregates(records, aggs)
        assert result["average"] == 187.5  # 750 / 4

    @pytest.mark.req("QUERY-AGG-001")
    def test_count_all(self, records: list[dict]) -> None:
        """Count all records."""
        aggs = {"count": AggregateFunc(count=True)}
        result = compute_aggregates(records, aggs)
        assert result["count"] == 4

    @pytest.mark.req("QUERY-AGG-001")
    def test_count_field(self) -> None:
        """Count non-null values of a field."""
        records = [
            {"name": "Alice", "email": "alice@test.com"},
            {"name": "Bob", "email": None},
            {"name": "Charlie", "email": "charlie@test.com"},
        ]
        aggs = {"emailCount": AggregateFunc(count="email")}
        result = compute_aggregates(records, aggs)
        assert result["emailCount"] == 2

    @pytest.mark.req("QUERY-AGG-002")
    def test_min_aggregate(self, records: list[dict]) -> None:
        """Compute minimum value."""
        aggs = {"minimum": AggregateFunc(min="amount")}
        result = compute_aggregates(records, aggs)
        assert result["minimum"] == 100

    @pytest.mark.req("QUERY-AGG-002")
    def test_max_aggregate(self, records: list[dict]) -> None:
        """Compute maximum value."""
        aggs = {"maximum": AggregateFunc(max="amount")}
        result = compute_aggregates(records, aggs)
        assert result["maximum"] == 300

    @pytest.mark.req("QUERY-AGG-003")
    def test_percentile_aggregate(self) -> None:
        """Compute percentile value."""
        records = [{"value": i} for i in range(1, 101)]  # 1 to 100
        aggs = {"p50": AggregateFunc(percentile={"field": "value", "p": 50})}
        result = compute_aggregates(records, aggs)
        # 50th percentile of 1-100 should be around 50
        assert 49 <= result["p50"] <= 51

    def test_first_aggregate(self, records: list[dict]) -> None:
        """Get first value of a field."""
        aggs = {"first": AggregateFunc(first="name")}
        result = compute_aggregates(records, aggs)
        assert result["first"] == "Alice"

    def test_last_aggregate(self, records: list[dict]) -> None:
        """Get last value of a field."""
        aggs = {"last": AggregateFunc(last="name")}
        result = compute_aggregates(records, aggs)
        assert result["last"] == "Diana"

    @pytest.mark.req("QUERY-AGG-005")
    def test_multiply_expression(self, records: list[dict]) -> None:
        """Compute multiplication of aggregates."""
        aggs = {
            "count": AggregateFunc(count=True),
            "avg": AggregateFunc(avg="amount"),
            "product": AggregateFunc(multiply=["count", "avg"]),
        }
        result = compute_aggregates(records, aggs)
        assert result["product"] == 4 * 187.5

    @pytest.mark.req("QUERY-AGG-005")
    def test_divide_expression(self, records: list[dict]) -> None:
        """Compute division of aggregates."""
        aggs = {
            "total": AggregateFunc(sum="amount"),
            "count": AggregateFunc(count=True),
            "computed_avg": AggregateFunc(divide=["total", "count"]),
        }
        result = compute_aggregates(records, aggs)
        assert result["computed_avg"] == 187.5

    @pytest.mark.req("QUERY-AGG-005")
    def test_add_expression(self, records: list[dict]) -> None:
        """Compute addition of aggregates and literals."""
        aggs = {
            "total": AggregateFunc(sum="amount"),
            "adjusted": AggregateFunc(add=["total", 100]),
        }
        result = compute_aggregates(records, aggs)
        assert result["adjusted"] == 850

    @pytest.mark.req("QUERY-AGG-005")
    def test_subtract_expression(self, records: list[dict]) -> None:
        """Compute subtraction."""
        aggs = {
            "total": AggregateFunc(sum="amount"),
            "discounted": AggregateFunc(subtract=["total", 50]),
        }
        result = compute_aggregates(records, aggs)
        assert result["discounted"] == 700

    def test_divide_by_zero(self) -> None:
        """Division by zero returns None."""
        aggs = {
            "zero": AggregateFunc(count="nonexistent"),  # Will be 0
            "value": AggregateFunc(sum="amount"),
            "result": AggregateFunc(divide=["value", "zero"]),
        }
        records = [{"amount": 100}]
        result = compute_aggregates(records, aggs)
        assert result["result"] is None

    def test_empty_records(self) -> None:
        """Aggregates on empty records."""
        aggs = {
            "sum": AggregateFunc(sum="amount"),
            "avg": AggregateFunc(avg="amount"),
            "count": AggregateFunc(count=True),
        }
        result = compute_aggregates([], aggs)
        assert result["sum"] == 0.0
        assert result["avg"] is None
        assert result["count"] == 0

    def test_multiple_aggregates(self, records: list[dict]) -> None:
        """Compute multiple aggregates at once."""
        aggs = {
            "sum": AggregateFunc(sum="amount"),
            "avg": AggregateFunc(avg="amount"),
            "min": AggregateFunc(min="amount"),
            "max": AggregateFunc(max="amount"),
            "count": AggregateFunc(count=True),
        }
        result = compute_aggregates(records, aggs)
        assert result["sum"] == 750
        assert result["avg"] == 187.5
        assert result["min"] == 100
        assert result["max"] == 300
        assert result["count"] == 4


class TestGroupAndAggregate:
    """Tests for group_and_aggregate function."""

    @pytest.fixture
    def records(self) -> list[dict]:
        """Sample records for testing."""
        return [
            {"category": "A", "amount": 100},
            {"category": "B", "amount": 200},
            {"category": "A", "amount": 150},
            {"category": "B", "amount": 300},
            {"category": "A", "amount": 50},
        ]

    @pytest.mark.req("QUERY-AGG-004")
    def test_group_by_single_field(self, records: list[dict]) -> None:
        """Group by single field and aggregate."""
        aggs = {
            "total": AggregateFunc(sum="amount"),
            "count": AggregateFunc(count=True),
        }
        results = group_and_aggregate(records, "category", aggs)

        # Should have 2 groups: A and B
        assert len(results) == 2

        # Find group A
        group_a = next(r for r in results if r["category"] == "A")
        assert group_a["total"] == 300  # 100 + 150 + 50
        assert group_a["count"] == 3

        # Find group B
        group_b = next(r for r in results if r["category"] == "B")
        assert group_b["total"] == 500  # 200 + 300
        assert group_b["count"] == 2

    def test_group_by_with_null_key(self) -> None:
        """Group by handles null keys with '(no value)' display and sorts to end."""
        records = [
            {"category": "A", "amount": 100},
            {"category": None, "amount": 200},
            {"category": "A", "amount": 50},
        ]
        aggs = {"count": AggregateFunc(count=True)}
        results = group_and_aggregate(records, "category", aggs)

        assert len(results) == 2
        # Null group should display as "(no value)" and appear at end
        null_group = results[-1]
        assert null_group["category"] == "(no value)"
        assert null_group["count"] == 1


class TestApplyHaving:
    """Tests for apply_having function."""

    @pytest.fixture
    def aggregated_results(self) -> list[dict]:
        """Sample aggregated results."""
        return [
            {"category": "A", "total": 300, "count": 3},
            {"category": "B", "total": 500, "count": 2},
            {"category": "C", "total": 100, "count": 1},
        ]

    def test_having_simple_condition(self, aggregated_results: list[dict]) -> None:
        """Apply simple HAVING condition."""
        having = HavingClause(path="total", op="gt", value=200)
        filtered = apply_having(aggregated_results, having)

        assert len(filtered) == 2
        assert all(r["total"] > 200 for r in filtered)

    def test_having_and_condition(self, aggregated_results: list[dict]) -> None:
        """Apply HAVING with AND condition."""
        having = HavingClause(
            and_=[
                HavingClause(path="total", op="gte", value=100),
                HavingClause(path="count", op="gte", value=2),
            ]
        )
        filtered = apply_having(aggregated_results, having)

        assert len(filtered) == 2
        # Only A and B have count >= 2
        categories = {r["category"] for r in filtered}
        assert categories == {"A", "B"}

    def test_having_or_condition(self, aggregated_results: list[dict]) -> None:
        """Apply HAVING with OR condition."""
        having = HavingClause(
            or_=[
                HavingClause(path="total", op="gt", value=400),
                HavingClause(path="count", op="eq", value=1),
            ]
        )
        filtered = apply_having(aggregated_results, having)

        # B (total > 400) and C (count == 1)
        assert len(filtered) == 2

    def test_having_empty_returns_all(self, aggregated_results: list[dict]) -> None:
        """HAVING with no conditions returns all results."""
        having = HavingClause()  # No path, no and_, no or_
        filtered = apply_having(aggregated_results, having)
        assert len(filtered) == 3


class TestAggregateEdgeCases:
    """Tests for edge cases in aggregate functions."""

    def test_sum_with_non_numeric_values(self) -> None:
        """Sum ignores non-numeric values."""
        records = [
            {"amount": 100},
            {"amount": "not a number"},
            {"amount": 200},
            {"amount": {"nested": "dict"}},
        ]
        aggs = {"total": AggregateFunc(sum="amount")}
        result = compute_aggregates(records, aggs)
        assert result["total"] == 300  # Only 100 + 200

    def test_avg_with_non_numeric_values(self) -> None:
        """Avg ignores non-numeric values."""
        records = [
            {"amount": 100},
            {"amount": "text"},
            {"amount": 200},
        ]
        aggs = {"average": AggregateFunc(avg="amount")}
        result = compute_aggregates(records, aggs)
        assert result["average"] == 150  # (100 + 200) / 2

    def test_min_with_empty_values(self) -> None:
        """Min returns None when all values are null."""
        records = [{"amount": None}, {"amount": None}]
        aggs = {"minimum": AggregateFunc(min="amount")}
        result = compute_aggregates(records, aggs)
        assert result["minimum"] is None

    def test_max_with_empty_values(self) -> None:
        """Max returns None when all values are null."""
        records = [{"amount": None}, {"amount": None}]
        aggs = {"maximum": AggregateFunc(max="amount")}
        result = compute_aggregates(records, aggs)
        assert result["maximum"] is None

    def test_count_with_false_field(self) -> None:
        """Count with field=False counts all records."""
        records = [{"a": 1}, {"a": 2}, {"a": 3}]
        aggs = {"count": AggregateFunc(count=False)}
        result = compute_aggregates(records, aggs)
        # False is not True and not a string, so falls through to len(records)
        assert result["count"] == 3

    def test_percentile_with_single_value(self) -> None:
        """Percentile with single value returns that value."""
        records = [{"value": 42}]
        aggs = {"p50": AggregateFunc(percentile={"field": "value", "p": 50})}
        result = compute_aggregates(records, aggs)
        assert result["p50"] == 42

    def test_percentile_with_non_numeric_values(self) -> None:
        """Percentile ignores non-numeric values."""
        records = [
            {"value": 10},
            {"value": "not a number"},
            {"value": 20},
        ]
        aggs = {"p50": AggregateFunc(percentile={"field": "value", "p": 50})}
        result = compute_aggregates(records, aggs)
        # Should compute percentile of [10, 20]
        assert result["p50"] is not None

    def test_percentile_with_all_non_numeric(self) -> None:
        """Percentile returns None when all values are non-numeric."""
        records = [{"value": "a"}, {"value": "b"}]
        aggs = {"p50": AggregateFunc(percentile={"field": "value", "p": 50})}
        result = compute_aggregates(records, aggs)
        assert result["p50"] is None

    def test_first_with_all_nulls(self) -> None:
        """First returns None when all values are null."""
        records = [{"name": None}, {"name": None}, {"name": None}]
        aggs = {"first": AggregateFunc(first="name")}
        result = compute_aggregates(records, aggs)
        assert result["first"] is None

    def test_last_with_all_nulls(self) -> None:
        """Last returns None when all values are null."""
        records = [{"name": None}, {"name": None}, {"name": None}]
        aggs = {"last": AggregateFunc(last="name")}
        result = compute_aggregates(records, aggs)
        assert result["last"] is None

    def test_first_skips_nulls(self) -> None:
        """First returns first non-null value."""
        records = [{"name": None}, {"name": None}, {"name": "Alice"}]
        aggs = {"first": AggregateFunc(first="name")}
        result = compute_aggregates(records, aggs)
        assert result["first"] == "Alice"

    def test_last_skips_nulls(self) -> None:
        """Last returns last non-null value."""
        records = [{"name": "Alice"}, {"name": None}, {"name": None}]
        aggs = {"last": AggregateFunc(last="name")}
        result = compute_aggregates(records, aggs)
        assert result["last"] == "Alice"


class TestExpressionAggregateEdgeCases:
    """Tests for expression aggregate edge cases."""

    def test_expression_with_none_operand(self) -> None:
        """Expression returns None if any operand is None."""
        aggs = {
            "avg": AggregateFunc(avg="missing_field"),  # Will be None
            "count": AggregateFunc(count=True),
            "product": AggregateFunc(multiply=["avg", "count"]),
        }
        records = [{"amount": 100}]
        result = compute_aggregates(records, aggs)
        assert result["product"] is None  # avg is None

    def test_expression_with_non_numeric_operand(self) -> None:
        """Expression returns None if operand can't be converted to float."""
        # First compute a first aggregate that returns a string
        aggs = {
            "first_name": AggregateFunc(first="name"),
            "count": AggregateFunc(count=True),
            "product": AggregateFunc(multiply=["first_name", "count"]),
        }
        records = [{"name": "Alice", "amount": 100}]
        result = compute_aggregates(records, aggs)
        assert result["product"] is None  # Can't multiply string

    def test_expression_with_single_operand(self) -> None:
        """Expression with less than 2 operands returns None."""
        # Need at least 2 operands for expression aggregates
        result = compute_aggregates([], {"single": AggregateFunc(multiply=[100])})
        assert result["single"] is None

    def test_expression_chain(self) -> None:
        """Expressions can reference other expressions."""
        aggs = {
            "sum": AggregateFunc(sum="amount"),
            "count": AggregateFunc(count=True),
            "avg_manual": AggregateFunc(divide=["sum", "count"]),
            "doubled": AggregateFunc(multiply=["avg_manual", 2]),
        }
        records = [{"amount": 100}, {"amount": 200}]
        result = compute_aggregates(records, aggs)
        assert result["doubled"] == 300  # (300/2) * 2


class TestGroupByEdgeCases:
    """Tests for group_and_aggregate edge cases."""

    def test_group_by_multi_select_normalizes_order(self) -> None:
        """Multi-select values with different orders are grouped together."""
        records = [
            {"tags": ["A", "B"], "amount": 100},
            {"tags": ["B", "A"], "amount": 200},  # Same tags, different order
            {"tags": ["A", "B"], "amount": 50},
        ]
        aggs = {"total": AggregateFunc(sum="amount")}
        results = group_and_aggregate(records, "tags", aggs)

        # All should be in one group because ["A", "B"] and ["B", "A"] normalize to same
        assert len(results) == 1
        assert results[0]["total"] == 350

    def test_group_by_with_unsortable_values(self) -> None:
        """Multi-select with unsortable values falls back to original order."""
        # Mix of types that can't be sorted together
        records = [
            {"tags": [1, "a"], "amount": 100},
            {"tags": [1, "a"], "amount": 200},
        ]
        aggs = {"total": AggregateFunc(sum="amount")}
        results = group_and_aggregate(records, "tags", aggs)

        # Should still work, using tuple order
        assert len(results) == 1
        assert results[0]["total"] == 300

    def test_group_by_scalar_value(self) -> None:
        """Group by scalar (non-list) values works normally."""
        records = [
            {"status": "Active", "amount": 100},
            {"status": "Active", "amount": 200},
            {"status": "Inactive", "amount": 50},
        ]
        aggs = {"total": AggregateFunc(sum="amount")}
        results = group_and_aggregate(records, "status", aggs)

        assert len(results) == 2

    def test_group_by_converts_tuple_back_to_list(self) -> None:
        """Group by multi-select converts tuple back to list for display."""
        records = [{"tags": ["X", "Y"], "amount": 100}]
        aggs = {"count": AggregateFunc(count=True)}
        results = group_and_aggregate(records, "tags", aggs)

        # The display key should be a list, not tuple
        assert results[0]["tags"] == ["X", "Y"]
        assert isinstance(results[0]["tags"], list)
