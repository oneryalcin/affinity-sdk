"""Tests for query safety guards.

Tests for unbounded quantifier query detection and --max-records validation.
"""

from __future__ import annotations

import pytest

from affinity.cli.query.exceptions import QueryValidationError
from affinity.cli.query.executor import validate_quantifier_query
from affinity.cli.query.models import Query
from affinity.cli.query.planner import QueryPlanner
from affinity.cli.query.schema import UNBOUNDED_ENTITIES


class TestUnboundedEntities:
    """Tests for UNBOUNDED_ENTITIES constant."""

    def test_unbounded_entities_includes_persons(self) -> None:
        """persons should be in unbounded entities."""
        assert "persons" in UNBOUNDED_ENTITIES

    def test_unbounded_entities_includes_companies(self) -> None:
        """companies should be in unbounded entities."""
        assert "companies" in UNBOUNDED_ENTITIES

    def test_unbounded_entities_includes_opportunities(self) -> None:
        """opportunities should be in unbounded entities."""
        assert "opportunities" in UNBOUNDED_ENTITIES

    def test_unbounded_entities_excludes_list_entries(self) -> None:
        """listEntries should NOT be in unbounded entities (bounded by list)."""
        assert "listEntries" not in UNBOUNDED_ENTITIES

    def test_unbounded_entities_excludes_lists(self) -> None:
        """lists should NOT be in unbounded entities (small)."""
        assert "lists" not in UNBOUNDED_ENTITIES


class TestValidateQuantifierQuery:
    """Tests for validate_quantifier_query function."""

    @pytest.mark.req("QUERY-SAFETY-001")
    def test_unbounded_query_requires_max_records(self) -> None:
        """Should reject unbounded quantifier query without --max-records."""
        # Query with _count on persons (unbounded)
        query = Query(
            **{
                "from": "persons",
                "where": {"path": "companies._count", "op": "gt", "value": 0},
            }
        )

        with pytest.raises(QueryValidationError) as exc_info:
            validate_quantifier_query(query, 10000, max_records_explicit=False)

        assert "require explicit --max-records" in str(exc_info.value)
        assert "persons" in str(exc_info.value)

    @pytest.mark.req("QUERY-SAFETY-002")
    def test_bounded_query_allowed_without_max_records(self) -> None:
        """listEntries with quantifier should work without explicit limit."""
        # listEntries is bounded by list size, not unbounded
        # Note: This test uses a where clause that would require relationship data
        # but the entity itself is bounded, so no error should be raised
        query = Query(
            **{
                "from": "listEntries",
                "where": {
                    "and": [
                        {"path": "listId", "op": "eq", "value": 123},
                        {"exists": {"from": "interactions"}},
                    ]
                },
            }
        )

        # Should NOT raise - listEntries is bounded
        validate_quantifier_query(query, 10000, max_records_explicit=False)

    @pytest.mark.req("QUERY-SAFETY-004")
    def test_explicit_max_records_allows_query(self) -> None:
        """Should allow query with explicit --max-records."""
        query = Query(
            **{
                "from": "persons",
                "where": {"path": "companies._count", "op": "gt", "value": 0},
            }
        )

        # Should NOT raise when max_records_explicit=True
        validate_quantifier_query(query, 100, max_records_explicit=True)

    def test_query_without_quantifier_allowed(self) -> None:
        """Query without quantifiers should be allowed without explicit limit."""
        query = Query(
            **{
                "from": "persons",
                "where": {"path": "firstName", "op": "eq", "value": "John"},
            }
        )

        # Should NOT raise - no quantifier filter
        validate_quantifier_query(query, 10000, max_records_explicit=False)

    def test_query_without_where_allowed(self) -> None:
        """Query without where clause should be allowed."""
        query = Query(**{"from": "persons", "limit": 10})

        # Should NOT raise - no where clause
        validate_quantifier_query(query, 10000, max_records_explicit=False)

    def test_exists_quantifier_requires_explicit_max_records(self) -> None:
        """exists_ quantifier on unbounded entity requires explicit --max-records."""
        query = Query(
            **{
                "from": "companies",
                "where": {"exists": {"from": "interactions"}},
            }
        )

        with pytest.raises(QueryValidationError):
            validate_quantifier_query(query, 10000, max_records_explicit=False)

    def test_all_quantifier_requires_explicit_max_records(self) -> None:
        """all_ quantifier on unbounded entity requires explicit --max-records."""
        query = Query(
            **{
                "from": "persons",
                "where": {
                    "all": {
                        "path": "companies",
                        "where": {"path": "domain", "op": "contains", "value": ".com"},
                    }
                },
            }
        )

        with pytest.raises(QueryValidationError):
            validate_quantifier_query(query, 10000, max_records_explicit=False)


class TestPlannerUnboundedWarnings:
    """Tests for planner warnings on unbounded quantifier queries."""

    @pytest.mark.req("QUERY-SAFETY-003")
    def test_dry_run_shows_unbounded_warning(self) -> None:
        """Dry-run should warn about unbounded entities (but not block)."""
        query = Query(
            **{
                "from": "persons",
                "where": {"path": "companies._count", "op": "gt", "value": 0},
            }
        )

        planner = QueryPlanner(max_records=10000)
        plan = planner.plan(query)

        # Should have warning about unbounded
        assert any("UNBOUNDED" in w for w in plan.warnings)
        # Should require explicit max_records
        assert plan.requires_explicit_max_records is True
        # total_api_calls should be "UNBOUNDED" string
        assert plan.total_api_calls == "UNBOUNDED"

    def test_bounded_entity_no_unbounded_warning(self) -> None:
        """listEntries should not show unbounded warning."""
        query = Query(
            **{
                "from": "listEntries",
                "where": {
                    "and": [
                        {"path": "listId", "op": "eq", "value": 123},
                        {"exists": {"from": "interactions"}},
                    ]
                },
            }
        )

        planner = QueryPlanner(max_records=10000)
        plan = planner.plan(query)

        # Should NOT have unbounded warning
        assert not any("UNBOUNDED" in w for w in plan.warnings)
        # Should NOT require explicit max_records
        assert plan.requires_explicit_max_records is False

    def test_query_without_quantifier_no_warning(self) -> None:
        """Query without quantifiers should not show unbounded warning."""
        query = Query(
            **{
                "from": "persons",
                "where": {"path": "firstName", "op": "eq", "value": "John"},
            }
        )

        planner = QueryPlanner(max_records=10000)
        plan = planner.plan(query)

        # Should NOT have unbounded warning
        assert not any("UNBOUNDED" in w for w in plan.warnings)
        # Should NOT require explicit max_records
        assert plan.requires_explicit_max_records is False


class TestDryRunJsonOutput:
    """Tests for dry-run JSON output format."""

    def test_unbounded_query_json_includes_note(self) -> None:
        """Unbounded query JSON should include estimatedApiCallsNote."""
        import json

        from affinity.cli.query.output import format_dry_run_json

        query = Query(
            **{
                "from": "companies",
                "where": {"path": "persons._count", "op": "gt", "value": 0},
            }
        )

        planner = QueryPlanner(max_records=10000)
        plan = planner.plan(query)
        output = json.loads(format_dry_run_json(plan))

        # Should have UNBOUNDED estimate
        assert output["execution"]["estimatedApiCalls"] == "UNBOUNDED"
        # Should have explanatory note
        assert "estimatedApiCallsNote" in output["execution"]
        assert "10K-100K+" in output["execution"]["estimatedApiCallsNote"]
        # Should indicate explicit max_records required
        assert output["execution"]["requiresExplicitMaxRecords"] is True

    def test_bounded_query_json_no_note(self) -> None:
        """Bounded query JSON should not include estimatedApiCallsNote."""
        import json

        from affinity.cli.query.output import format_dry_run_json

        query = Query(
            **{
                "from": "persons",
                "where": {"path": "firstName", "op": "eq", "value": "John"},
                "limit": 10,
            }
        )

        planner = QueryPlanner(max_records=10000)
        plan = planner.plan(query)
        output = json.loads(format_dry_run_json(plan))

        # Should have numeric estimate
        assert isinstance(output["execution"]["estimatedApiCalls"], int)
        # Should NOT have note (only for unbounded)
        assert "estimatedApiCallsNote" not in output["execution"]
        # Should NOT require explicit max_records
        assert output["execution"]["requiresExplicitMaxRecords"] is False
