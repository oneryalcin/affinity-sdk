"""Tests for the query planner."""

from __future__ import annotations

import pytest

from affinity.cli.query import (
    QueryPlanner,
    QueryValidationError,
    create_planner,
    parse_query,
)


class TestQueryPlanner:
    """Tests for QueryPlanner class."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner(max_records=10000, concurrency=10)

    @pytest.mark.req("QUERY-PLAN-001")
    def test_plan_generates_fetch_step(self, planner: QueryPlanner) -> None:
        """Plan generates fetch step for primary entity."""
        result = parse_query({"from": "persons", "limit": 10})
        plan = planner.plan(result.query)

        assert len(plan.steps) >= 1
        assert plan.steps[0].operation == "fetch"
        assert plan.steps[0].entity == "persons"

    @pytest.mark.req("QUERY-PLAN-002")
    def test_plan_estimates_n_plus_1_for_includes(self, planner: QueryPlanner) -> None:
        """Plan estimates N+1 API calls for includes."""
        result = parse_query(
            {
                "from": "persons",
                "include": ["companies"],
            }
        )
        plan = planner.plan(result.query)

        include_steps = [s for s in plan.steps if s.operation == "include"]
        assert len(include_steps) == 1
        assert include_steps[0].estimated_api_calls > 0
        assert include_steps[0].relationship == "companies"

    @pytest.mark.req("QUERY-PLAN-003")
    def test_plan_warns_on_expensive_operations(self, planner: QueryPlanner) -> None:
        """Plan warns on expensive operations."""
        result = parse_query(
            {
                "from": "persons",
                "include": ["companies", "opportunities", "interactions"],
            }
        )
        plan = planner.plan(result.query)

        # Should have warnings about API calls
        assert plan.has_expensive_operations or len(plan.warnings) > 0

    @pytest.mark.req("QUERY-PLAN-004")
    def test_plan_dependencies_correct(self, planner: QueryPlanner) -> None:
        """Plan generates correct step dependencies."""
        result = parse_query(
            {
                "from": "persons",
                "where": {"path": "email", "op": "eq", "value": "x@test.com"},
                "include": ["companies"],
                "limit": 10,
            }
        )
        plan = planner.plan(result.query)

        # First step has no dependencies
        assert len(plan.steps[0].depends_on) == 0

        # Subsequent steps depend on previous
        for i, step in enumerate(plan.steps[1:], start=1):
            assert len(step.depends_on) > 0
            # All dependencies should be earlier steps
            assert all(dep < i for dep in step.depends_on)

    @pytest.mark.req("QUERY-PLAN-005")
    def test_plan_calculates_total_api_calls(self, planner: QueryPlanner) -> None:
        """Plan calculates total estimated API calls."""
        result = parse_query(
            {
                "from": "persons",
                "include": ["companies"],
                "limit": 10,
            }
        )
        plan = planner.plan(result.query)

        assert plan.total_api_calls > 0
        assert plan.total_api_calls == sum(s.estimated_api_calls for s in plan.steps)

    def test_plan_simple_fetch_and_limit(self, planner: QueryPlanner) -> None:
        """Simple query generates fetch and limit steps."""
        result = parse_query({"from": "persons", "limit": 10})
        plan = planner.plan(result.query)

        operations = [s.operation for s in plan.steps]
        assert "fetch" in operations
        assert "limit" in operations

    def test_plan_with_filter_adds_filter_step(self, planner: QueryPlanner) -> None:
        """Query with WHERE adds filter step."""
        result = parse_query(
            {
                "from": "persons",
                "where": {"path": "email", "op": "contains", "value": "@test.com"},
            }
        )
        plan = planner.plan(result.query)

        filter_steps = [s for s in plan.steps if s.operation == "filter"]
        assert len(filter_steps) == 1
        assert filter_steps[0].is_client_side

    def test_plan_with_sort_adds_sort_step(self, planner: QueryPlanner) -> None:
        """Query with orderBy adds sort step."""
        result = parse_query(
            {
                "from": "persons",
                "orderBy": [{"field": "lastName", "direction": "asc"}],
            }
        )
        plan = planner.plan(result.query)

        sort_steps = [s for s in plan.steps if s.operation == "sort"]
        assert len(sort_steps) == 1
        assert sort_steps[0].is_client_side

    def test_plan_with_aggregate_adds_aggregate_step(self, planner: QueryPlanner) -> None:
        """Query with aggregate adds aggregate step."""
        result = parse_query(
            {
                "from": "opportunities",
                "aggregate": {"total": {"count": True}},
            }
        )
        plan = planner.plan(result.query)

        agg_steps = [s for s in plan.steps if s.operation == "aggregate"]
        assert len(agg_steps) == 1
        assert agg_steps[0].is_client_side

    def test_plan_rejects_unknown_include(self, planner: QueryPlanner) -> None:
        """Plan rejects unknown include relationship with helpful error."""
        result = parse_query(
            {
                "from": "persons",
                "include": ["unknownRelation"],
            }
        )

        with pytest.raises(QueryValidationError) as exc:
            planner.plan(result.query)
        error_msg = str(exc.value)
        # Error should mention the unknown relationship
        assert "unknownRelation" in error_msg
        # Error should suggest available relationships
        assert "Available:" in error_msg
        assert "companies" in error_msg  # persons can include companies

    def test_plan_estimates_memory(self, planner: QueryPlanner) -> None:
        """Plan estimates memory usage."""
        result = parse_query({"from": "persons"})
        plan = planner.plan(result.query)

        assert plan.estimated_memory_mb is not None
        assert plan.estimated_memory_mb > 0

    def test_plan_with_limit_reduces_estimates(self, planner: QueryPlanner) -> None:
        """Limit reduces record estimates."""
        result_no_limit = parse_query({"from": "persons"})
        result_with_limit = parse_query({"from": "persons", "limit": 10})

        plan_no_limit = planner.plan(result_no_limit.query)
        plan_with_limit = planner.plan(result_with_limit.query)

        assert plan_with_limit.estimated_records_fetched <= plan_no_limit.estimated_records_fetched

    def test_plan_different_entities(self, planner: QueryPlanner) -> None:
        """Plan works for different entity types that support direct querying."""
        # Only GLOBAL entities can be queried directly without filters
        entities = ["persons", "companies", "opportunities", "lists"]

        for entity in entities:
            result = parse_query({"from": entity, "limit": 10})
            plan = planner.plan(result.query)
            assert plan.steps[0].entity == entity

    def test_plan_listentries_with_filter(self, planner: QueryPlanner) -> None:
        """Plan works for listEntries with required listId filter."""
        result = parse_query(
            {
                "from": "listEntries",
                "where": {"path": "listId", "op": "eq", "value": 123},
                "limit": 10,
            }
        )
        plan = planner.plan(result.query)
        assert plan.steps[0].entity == "listEntries"


class TestExecutionLevels:
    """Tests for execution level computation."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner()

    def test_get_execution_levels_simple(self, planner: QueryPlanner) -> None:
        """Simple query has sequential levels."""
        result = parse_query({"from": "persons", "limit": 10})
        plan = planner.plan(result.query)
        levels = planner.get_execution_levels(plan)

        # Each level should have at least one step
        assert len(levels) > 0
        for level in levels:
            assert len(level) >= 1

        # Total steps across levels should match plan steps
        total_steps = sum(len(level) for level in levels)
        assert total_steps == len(plan.steps)

    def test_get_execution_levels_respects_dependencies(self, planner: QueryPlanner) -> None:
        """Execution levels respect step dependencies."""
        result = parse_query(
            {
                "from": "persons",
                "where": {"path": "email", "op": "eq", "value": "x"},
                "include": ["companies"],
                "limit": 10,
            }
        )
        plan = planner.plan(result.query)
        levels = planner.get_execution_levels(plan)

        # Build step_id -> level mapping
        step_to_level: dict[int, int] = {}
        for level_idx, level in enumerate(levels):
            for step in level:
                step_to_level[step.step_id] = level_idx

        # Verify each step appears after its dependencies
        for step in plan.steps:
            for dep_id in step.depends_on:
                assert step_to_level[dep_id] < step_to_level[step.step_id]


class TestUnknownEntity:
    """Tests for unknown entity type handling."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner()

    def test_plan_unknown_entity_raises_error(self, planner: QueryPlanner) -> None:
        """Planning a query with unknown entity type raises QueryValidationError."""
        from affinity.cli.query.models import Query

        query = Query(from_="unknownEntity")
        with pytest.raises(QueryValidationError) as exc:
            planner.plan(query)
        assert "Unknown entity type 'unknownEntity'" in str(exc.value)
        assert exc.value.field == "from"


class TestEntityWithoutRelationships:
    """Tests for entities that don't support includes."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner()

    def test_plan_include_on_entity_without_relationships(
        self, planner: QueryPlanner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Planning include on entity without relationships raises error."""
        from affinity.cli.query import planner as planner_module
        from affinity.cli.query.models import Query
        from affinity.cli.query.schema import EntitySchema

        # Create a mock entity schema with no relationships (using dataclass fields)
        mock_schema = EntitySchema(
            name="testEntity",
            service_attr="test_entities",
            id_field="id",
            filterable_fields=frozenset(["id", "name"]),
            computed_fields=frozenset(),
            relationships={},  # No relationships
        )

        original_get_schema = planner_module.get_entity_schema
        original_get_rel = planner_module.get_relationship

        def mock_get_entity_schema(entity_type: str) -> EntitySchema | None:
            if entity_type == "testEntity":
                return mock_schema
            return original_get_schema(entity_type)

        def mock_get_relationship(entity_type: str, rel_name: str):
            if entity_type == "testEntity":
                return None
            return original_get_rel(entity_type, rel_name)

        # Patch on planner module since that's where they're imported
        monkeypatch.setattr(planner_module, "get_entity_schema", mock_get_entity_schema)
        monkeypatch.setattr(planner_module, "get_relationship", mock_get_relationship)

        query = Query(from_="testEntity", include=["something"])
        with pytest.raises(QueryValidationError) as exc:
            planner.plan(query)
        assert "does not support includes" in str(exc.value)
        assert exc.value.field == "include"


class TestNPlusOneWarnings:
    """Tests for N+1 include warnings."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner()

    def test_n_plus_one_include_generates_warning(self, planner: QueryPlanner) -> None:
        """Include that requires N+1 generates step warning."""
        result = parse_query(
            {
                "from": "persons",
                "include": ["companies"],
                "limit": 5,
            }
        )
        plan = planner.plan(result.query)

        include_steps = [s for s in plan.steps if s.operation == "include"]
        assert len(include_steps) == 1
        # The step should have warnings about N+1 calls
        assert len(include_steps[0].warnings) > 0
        assert "API calls" in include_steps[0].warnings[0]

    def test_global_service_include_no_n_plus_one_warning(
        self, planner: QueryPlanner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Include using global service strategy has no N+1 warning."""
        from affinity.cli.query import planner as planner_module
        from affinity.cli.query.schema import RelationshipDef

        original_get_rel = planner_module.get_relationship

        def mock_get_relationship(entity_type: str, rel_name: str):
            if entity_type == "persons" and rel_name == "companies":
                # Return a relationship that doesn't require N+1
                return RelationshipDef(
                    target_entity="companies",
                    fetch_strategy="global_service",
                    method_or_service="companies",
                    requires_n_plus_1=False,
                )
            return original_get_rel(entity_type, rel_name)

        # Patch on planner module since that's where it's imported
        monkeypatch.setattr(planner_module, "get_relationship", mock_get_relationship)

        result = parse_query(
            {
                "from": "persons",
                "include": ["companies"],
                "limit": 5,
            }
        )
        plan = planner.plan(result.query)

        include_steps = [s for s in plan.steps if s.operation == "include"]
        assert len(include_steps) == 1
        # No N+1 warnings for global service
        assert len(include_steps[0].warnings) == 0
        # Estimated API calls should be 1 (single global call)
        assert include_steps[0].estimated_api_calls == 1


class TestCountConditions:
    """Tests for condition counting in WHERE clauses."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner()

    def test_count_conditions_with_or_clause(self, planner: QueryPlanner) -> None:
        """OR clause counts conditions correctly."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "or": [
                        {"path": "firstName", "op": "eq", "value": "John"},
                        {"path": "firstName", "op": "eq", "value": "Jane"},
                        {"path": "firstName", "op": "eq", "value": "Bob"},
                    ]
                },
            }
        )
        plan = planner.plan(result.query)

        # OR clause with 3 conditions should have filter step
        filter_steps = [s for s in plan.steps if s.operation == "filter"]
        assert len(filter_steps) == 1
        # Check description mentions OR
        assert "OR" in filter_steps[0].description
        assert "3 conditions" in filter_steps[0].description

    def test_count_conditions_with_not_clause(self, planner: QueryPlanner) -> None:
        """NOT clause counts conditions correctly."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "not": {"path": "email", "op": "is_null"},
                },
            }
        )
        plan = planner.plan(result.query)

        # NOT clause should have filter step
        filter_steps = [s for s in plan.steps if s.operation == "filter"]
        assert len(filter_steps) == 1
        # Estimated records should be reduced (condition counted)
        assert filter_steps[0].estimated_records is not None
        assert filter_steps[0].estimated_records < 5000  # Base estimate


class TestDescribeWhere:
    """Tests for WHERE clause description generation."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner()

    def test_describe_where_unary_is_null(self, planner: QueryPlanner) -> None:
        """Unary is_null operator described correctly."""
        result = parse_query(
            {
                "from": "persons",
                "where": {"path": "email", "op": "is_null"},
            }
        )
        plan = planner.plan(result.query)

        filter_steps = [s for s in plan.steps if s.operation == "filter"]
        assert len(filter_steps) == 1
        # Description should not include value for unary op
        assert "is_null" in filter_steps[0].description
        assert "email" in filter_steps[0].description

    def test_describe_where_unary_is_not_null(self, planner: QueryPlanner) -> None:
        """Unary is_not_null operator described correctly."""
        result = parse_query(
            {
                "from": "persons",
                "where": {"path": "email", "op": "is_not_null"},
            }
        )
        plan = planner.plan(result.query)

        filter_steps = [s for s in plan.steps if s.operation == "filter"]
        assert len(filter_steps) == 1
        assert "is_not_null" in filter_steps[0].description

    def test_describe_where_or_condition(self, planner: QueryPlanner) -> None:
        """OR condition described correctly."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "or": [
                        {"path": "firstName", "op": "eq", "value": "John"},
                        {"path": "firstName", "op": "eq", "value": "Jane"},
                    ]
                },
            }
        )
        plan = planner.plan(result.query)

        filter_steps = [s for s in plan.steps if s.operation == "filter"]
        assert len(filter_steps) == 1
        assert "2 conditions (OR)" in filter_steps[0].description

    def test_describe_where_not_condition(self, planner: QueryPlanner) -> None:
        """NOT condition described correctly."""
        result = parse_query(
            {
                "from": "persons",
                "where": {
                    "not": {"path": "email", "op": "eq", "value": "test@test.com"},
                },
            }
        )
        plan = planner.plan(result.query)

        filter_steps = [s for s in plan.steps if s.operation == "filter"]
        assert len(filter_steps) == 1
        assert "NOT condition" in filter_steps[0].description


class TestFilterPushdown:
    """Tests for filter pushdown optimization."""

    @pytest.fixture
    def planner(self) -> QueryPlanner:
        """Create a planner for testing."""
        return create_planner()

    @pytest.mark.req("QUERY-OPT-001")
    def test_identifies_pushdown_for_list_entries(self, planner: QueryPlanner) -> None:
        """Identifies filter pushdown for listEntries."""
        result = parse_query(
            {
                "from": "listEntries",
                "where": {
                    "and": [
                        {"path": "listId", "op": "eq", "value": 123},
                        {"path": "fields.Status", "op": "eq", "value": "Active"},
                    ]
                },
            }
        )
        plan = planner.plan(result.query)

        fetch_step = plan.steps[0]
        assert fetch_step.filter_pushdown is True
        assert fetch_step.pushdown_filter is not None

    @pytest.mark.req("QUERY-OPT-002")
    def test_generates_pushdown_filter_string(self, planner: QueryPlanner) -> None:
        """Generates correct pushdown filter string."""
        result = parse_query(
            {
                "from": "listEntries",
                "where": {
                    "and": [
                        {"path": "listId", "op": "eq", "value": 123},
                        {"path": "fields.Status", "op": "eq", "value": "Active"},
                    ]
                },
            }
        )
        plan = planner.plan(result.query)

        fetch_step = plan.steps[0]
        assert fetch_step.pushdown_filter == "Status=Active"

    @pytest.mark.req("QUERY-OPT-003")
    def test_warns_when_no_pushdown_available(self, planner: QueryPlanner) -> None:
        """Warns when no pushdown is available."""
        result = parse_query(
            {
                "from": "listEntries",
                "where": {
                    "and": [
                        {"path": "listId", "op": "eq", "value": 123},
                        {"path": "name", "op": "contains", "value": "test"},
                    ]
                },
            }
        )
        plan = planner.plan(result.query)

        # Should have warning about no server-side filtering
        assert any("server-side" in w.lower() for w in plan.warnings)

    def test_no_pushdown_for_non_list_entries(self, planner: QueryPlanner) -> None:
        """No pushdown optimization for non-listEntries entities."""
        result = parse_query(
            {
                "from": "persons",
                "where": {"path": "email", "op": "eq", "value": "test@test.com"},
            }
        )
        plan = planner.plan(result.query)

        fetch_step = plan.steps[0]
        assert fetch_step.filter_pushdown is False

    def test_no_pushdown_for_complex_operators(self, planner: QueryPlanner) -> None:
        """No pushdown for complex operators like contains."""
        result = parse_query(
            {
                "from": "listEntries",
                "where": {
                    "and": [
                        {"path": "listId", "op": "eq", "value": 123},
                        {"path": "fields.Status", "op": "contains", "value": "Act"},
                    ]
                },
            }
        )
        plan = planner.plan(result.query)

        fetch_step = plan.steps[0]
        assert fetch_step.filter_pushdown is False

    def test_no_pushdown_when_path_is_none(self, planner: QueryPlanner) -> None:
        """No pushdown when WHERE condition has no path (e.g., expression)."""
        from affinity.cli.query.models import Query, WhereClause

        # Create WHERE clause with no path (simulating an expression condition)
        where = WhereClause(op="eq", value=True)  # No path
        query = Query(from_="listEntries", where=where)
        plan = planner.plan(query)

        fetch_step = plan.steps[0]
        # Should not crash and should have no pushdown
        assert fetch_step.filter_pushdown is False
