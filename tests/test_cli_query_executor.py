"""Tests for query executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from affinity.cli.query import (
    QueryExecutionError,
    QuerySafetyLimitError,
    QueryTimeoutError,
)
from affinity.cli.query.executor import (
    ExecutionContext,
    NullProgressCallback,
    QueryExecutor,
    QueryProgressCallback,
    execute_query,
)
from affinity.cli.query.models import (
    AggregateFunc,
    ExecutionPlan,
    OrderByClause,
    PlanStep,
    Query,
    WhereClause,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncAffinity client."""
    client = AsyncMock()
    client.whoami = AsyncMock(return_value={"id": 1, "email": "test@test.com"})
    return client


def create_mock_record(data: dict) -> MagicMock:
    """Create a mock record with proper model_dump."""
    record = MagicMock()
    record.model_dump = MagicMock(return_value=data)
    return record


def create_mock_page_iterator(records: list[dict]):
    """Create a mock page iterator for testing."""

    class MockPageIterator:
        def pages(self, on_progress=None):
            async def generator():
                page = MagicMock()
                page.data = [create_mock_record(r) for r in records]
                if on_progress:
                    from affinity.models.pagination import PaginationProgress  # noqa: PLC0415

                    on_progress(
                        PaginationProgress(
                            page_number=1,
                            items_in_page=len(records),
                            items_so_far=len(records),
                            has_next=False,
                        )
                    )
                yield page

            return generator()

    return MockPageIterator()


@pytest.fixture
def mock_service() -> MagicMock:
    """Create a mock service with paginated results."""
    service = MagicMock()

    records = [
        {"id": 1, "name": "Alice", "email": "alice@test.com"},
        {"id": 2, "name": "Bob", "email": "bob@test.com"},
    ]
    service.all.return_value = create_mock_page_iterator(records)
    return service


@pytest.fixture
def simple_query() -> Query:
    """Create a simple query for testing."""
    return Query(from_="persons", limit=10)


@pytest.fixture
def simple_plan(simple_query: Query) -> ExecutionPlan:
    """Create a simple execution plan."""
    return ExecutionPlan(
        query=simple_query,
        steps=[
            PlanStep(
                step_id=0,
                operation="fetch",
                entity="persons",
                description="Fetch persons",
                estimated_api_calls=1,
            ),
            PlanStep(
                step_id=1,
                operation="limit",
                description="Limit to 10",
                depends_on=[0],
            ),
        ],
        total_api_calls=1,
        estimated_records_fetched=10,
        estimated_memory_mb=0.01,
        warnings=[],
        recommendations=[],
        has_expensive_operations=False,
        requires_full_scan=False,
    )


# =============================================================================
# ExecutionContext Tests
# =============================================================================


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_check_timeout_no_error(self, simple_query: Query) -> None:
        """No error when within timeout."""
        ctx = ExecutionContext(query=simple_query)
        # Should not raise
        ctx.check_timeout(300.0)

    def test_check_timeout_raises(self, simple_query: Query) -> None:
        """Raises QueryTimeoutError when exceeded."""
        ctx = ExecutionContext(query=simple_query)
        ctx.start_time = 0  # Started at epoch
        with pytest.raises(QueryTimeoutError) as exc:
            ctx.check_timeout(1.0)
        assert "exceeded timeout" in str(exc.value)

    def test_check_max_records_no_error(self, simple_query: Query) -> None:
        """No error when under limit."""
        ctx = ExecutionContext(query=simple_query, max_records=100)
        ctx.records = [{"id": i} for i in range(50)]
        # Should not raise
        ctx.check_max_records()

    def test_check_max_records_raises(self, simple_query: Query) -> None:
        """Raises QuerySafetyLimitError when exceeded."""
        ctx = ExecutionContext(query=simple_query, max_records=10)
        ctx.records = [{"id": i} for i in range(10)]
        with pytest.raises(QuerySafetyLimitError) as exc:
            ctx.check_max_records()
        assert "10 records" in str(exc.value)

    def test_build_result(self, simple_query: Query) -> None:
        """Builds QueryResult correctly."""
        ctx = ExecutionContext(query=simple_query)
        ctx.records = [{"id": 1}, {"id": 2}]
        ctx.included = {"companies": [{"id": 10}]}

        result = ctx.build_result()

        assert len(result.data) == 2
        assert result.included == {"companies": [{"id": 10}]}
        assert result.meta["recordCount"] == 2


# =============================================================================
# QueryExecutor Tests
# =============================================================================


class TestQueryExecutor:
    """Tests for QueryExecutor."""

    @pytest.mark.req("QUERY-EXEC-001")
    @pytest.mark.asyncio
    async def test_execute_simple_fetch_and_limit(
        self, mock_client: AsyncMock, mock_service: AsyncMock, simple_plan: ExecutionPlan
    ) -> None:
        """Execute simple fetch + limit query."""
        mock_client.persons = mock_service

        executor = QueryExecutor(mock_client, max_records=100)
        result = await executor.execute(simple_plan)

        assert len(result.data) == 2
        assert result.data[0]["name"] == "Alice"
        mock_client.whoami.assert_called_once()

    @pytest.mark.req("QUERY-EXEC-002")
    @pytest.mark.asyncio
    async def test_execute_client_side_filtering(
        self, mock_client: AsyncMock, mock_service: AsyncMock
    ) -> None:
        """Execute query with client-side filtering."""
        mock_client.persons = mock_service

        query = Query(
            from_="persons",
            where=WhereClause(path="name", op="eq", value="Alice"),
        )
        plan = ExecutionPlan(
            query=query,
            steps=[
                PlanStep(
                    step_id=0,
                    operation="fetch",
                    entity="persons",
                    description="Fetch",
                    estimated_api_calls=1,
                ),
                PlanStep(step_id=1, operation="filter", description="Filter", depends_on=[0]),
            ],
            total_api_calls=1,
            estimated_records_fetched=1,
            estimated_memory_mb=0.01,
            warnings=[],
            recommendations=[],
            has_expensive_operations=False,
            requires_full_scan=False,
        )

        executor = QueryExecutor(mock_client)
        result = await executor.execute(plan)

        # Should only have Alice after filtering
        assert len(result.data) == 1
        assert result.data[0]["name"] == "Alice"

    @pytest.mark.req("QUERY-EXEC-004")
    @pytest.mark.asyncio
    async def test_execute_aggregations(self, mock_client: AsyncMock) -> None:
        """Execute query with aggregation."""
        # Create service that returns records with amounts
        service = MagicMock()
        records = [
            {"id": 1, "amount": 100},
            {"id": 2, "amount": 200},
            {"id": 3, "amount": 300},
        ]
        service.all.return_value = create_mock_page_iterator(records)
        mock_client.opportunities = service

        query = Query(
            from_="opportunities",
            aggregate={"total": AggregateFunc(sum="amount"), "count": AggregateFunc(count=True)},
        )
        plan = ExecutionPlan(
            query=query,
            steps=[
                PlanStep(
                    step_id=0,
                    operation="fetch",
                    entity="opportunities",
                    description="Fetch",
                    estimated_api_calls=1,
                ),
                PlanStep(step_id=1, operation="aggregate", description="Aggregate", depends_on=[0]),
            ],
            total_api_calls=1,
            estimated_records_fetched=3,
            estimated_memory_mb=0.01,
            warnings=[],
            recommendations=[],
            has_expensive_operations=False,
            requires_full_scan=False,
        )

        executor = QueryExecutor(mock_client)
        result = await executor.execute(plan)

        assert len(result.data) == 1
        assert result.data[0]["total"] == 600
        assert result.data[0]["count"] == 3

    @pytest.mark.req("QUERY-EXEC-005")
    @pytest.mark.asyncio
    async def test_reports_progress_callbacks(
        self, mock_client: AsyncMock, mock_service: AsyncMock, simple_plan: ExecutionPlan
    ) -> None:
        """Progress callbacks are invoked."""
        mock_client.persons = mock_service

        progress = MagicMock(spec=QueryProgressCallback)

        executor = QueryExecutor(mock_client, progress=progress)
        await executor.execute(simple_plan)

        # Should have called on_step_start for each step
        assert progress.on_step_start.call_count == 2
        # Should have called on_step_complete for each step
        assert progress.on_step_complete.call_count == 2

    @pytest.mark.req("QUERY-EXEC-007")
    @pytest.mark.asyncio
    async def test_enforce_max_records_limit(self, mock_client: AsyncMock) -> None:
        """Stops fetching when max_records reached."""
        # Create service that returns many records across multiple pages
        service = MagicMock()

        class MultiPageIterator:
            def pages(self, _on_progress=None):
                async def generator():
                    for i in range(10):
                        page = MagicMock()
                        page.data = [create_mock_record({"id": i * 10 + j}) for j in range(10)]
                        yield page

                return generator()

        service.all.return_value = MultiPageIterator()
        mock_client.persons = service

        query = Query(from_="persons")
        plan = ExecutionPlan(
            query=query,
            steps=[
                PlanStep(
                    step_id=0,
                    operation="fetch",
                    entity="persons",
                    description="Fetch",
                    estimated_api_calls=10,
                ),
            ],
            total_api_calls=10,
            estimated_records_fetched=100,
            estimated_memory_mb=0.1,
            warnings=[],
            recommendations=[],
            has_expensive_operations=False,
            requires_full_scan=True,
        )

        executor = QueryExecutor(mock_client, max_records=25)
        result = await executor.execute(plan)

        # Should stop at max_records
        assert len(result.data) <= 25

    @pytest.mark.req("QUERY-EXEC-009")
    @pytest.mark.asyncio
    async def test_limit_propagation_stops_early(
        self, mock_client: AsyncMock, mock_service: AsyncMock
    ) -> None:
        """Query limit stops fetching early."""
        mock_client.persons = mock_service

        query = Query(from_="persons", limit=1)
        plan = ExecutionPlan(
            query=query,
            steps=[
                PlanStep(
                    step_id=0,
                    operation="fetch",
                    entity="persons",
                    description="Fetch",
                    estimated_api_calls=1,
                ),
                PlanStep(step_id=1, operation="limit", description="Limit", depends_on=[0]),
            ],
            total_api_calls=1,
            estimated_records_fetched=1,
            estimated_memory_mb=0.01,
            warnings=[],
            recommendations=[],
            has_expensive_operations=False,
            requires_full_scan=False,
        )

        executor = QueryExecutor(mock_client)
        result = await executor.execute(plan)

        assert len(result.data) == 1


class TestQueryExecutorSorting:
    """Tests for sort step execution."""

    @pytest.mark.asyncio
    async def test_sort_ascending(self, mock_client: AsyncMock) -> None:
        """Sort records in ascending order."""
        service = MagicMock()
        records = [
            {"id": 1, "name": "Charlie"},
            {"id": 2, "name": "Alice"},
            {"id": 3, "name": "Bob"},
        ]
        service.all.return_value = create_mock_page_iterator(records)
        mock_client.persons = service

        query = Query(
            from_="persons",
            order_by=[OrderByClause(field="name", direction="asc")],
        )
        plan = ExecutionPlan(
            query=query,
            steps=[
                PlanStep(
                    step_id=0,
                    operation="fetch",
                    entity="persons",
                    description="Fetch",
                    estimated_api_calls=1,
                ),
                PlanStep(step_id=1, operation="sort", description="Sort", depends_on=[0]),
            ],
            total_api_calls=1,
            estimated_records_fetched=3,
            estimated_memory_mb=0.01,
            warnings=[],
            recommendations=[],
            has_expensive_operations=False,
            requires_full_scan=False,
        )

        executor = QueryExecutor(mock_client)
        result = await executor.execute(plan)

        assert result.data[0]["name"] == "Alice"
        assert result.data[1]["name"] == "Bob"
        assert result.data[2]["name"] == "Charlie"

    @pytest.mark.asyncio
    async def test_sort_descending(self, mock_client: AsyncMock) -> None:
        """Sort records in descending order."""
        service = MagicMock()
        records = [
            {"id": 1, "value": 10},
            {"id": 2, "value": 30},
            {"id": 3, "value": 20},
        ]
        service.all.return_value = create_mock_page_iterator(records)
        mock_client.persons = service

        query = Query(
            from_="persons",
            order_by=[OrderByClause(field="value", direction="desc")],
        )
        plan = ExecutionPlan(
            query=query,
            steps=[
                PlanStep(
                    step_id=0,
                    operation="fetch",
                    entity="persons",
                    description="Fetch",
                    estimated_api_calls=1,
                ),
                PlanStep(step_id=1, operation="sort", description="Sort", depends_on=[0]),
            ],
            total_api_calls=1,
            estimated_records_fetched=3,
            estimated_memory_mb=0.01,
            warnings=[],
            recommendations=[],
            has_expensive_operations=False,
            requires_full_scan=False,
        )

        executor = QueryExecutor(mock_client)
        result = await executor.execute(plan)

        assert result.data[0]["value"] == 30
        assert result.data[1]["value"] == 20
        assert result.data[2]["value"] == 10


class TestQueryExecutorErrors:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_auth_failure(self, mock_client: AsyncMock, simple_plan: ExecutionPlan) -> None:
        """Auth failure raises QueryExecutionError."""
        mock_client.whoami.side_effect = Exception("Unauthorized")

        executor = QueryExecutor(mock_client)
        with pytest.raises(QueryExecutionError) as exc:
            await executor.execute(simple_plan)
        assert "Authentication failed" in str(exc.value)

    @pytest.mark.asyncio
    async def test_fetch_error(self, mock_client: AsyncMock, simple_plan: ExecutionPlan) -> None:
        """Fetch error raises QueryExecutionError."""
        service = MagicMock()

        class ErrorPageIterator:
            def pages(self, _on_progress=None):
                async def generator():
                    raise Exception("API Error")
                    yield  # Make it a generator

                return generator()

        service.all.return_value = ErrorPageIterator()
        mock_client.persons = service

        executor = QueryExecutor(mock_client)
        with pytest.raises(QueryExecutionError) as exc:
            await executor.execute(simple_plan)
        assert "Failed to fetch" in str(exc.value)


class TestNullProgressCallback:
    """Tests for NullProgressCallback."""

    def test_no_op_methods(self) -> None:
        """All methods are no-ops."""
        callback = NullProgressCallback()
        step = PlanStep(step_id=0, operation="fetch", description="test")

        # Should not raise
        callback.on_step_start(step)
        callback.on_step_progress(step, 10, 100)
        callback.on_step_complete(step, 10)
        callback.on_step_error(step, Exception("test"))


class TestExecuteQueryFunction:
    """Tests for execute_query convenience function."""

    @pytest.mark.asyncio
    async def test_convenience_function(
        self, mock_client: AsyncMock, mock_service: AsyncMock, simple_plan: ExecutionPlan
    ) -> None:
        """execute_query convenience function works."""
        mock_client.persons = mock_service

        result = await execute_query(mock_client, simple_plan)

        assert len(result.data) == 2
