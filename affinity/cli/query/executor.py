"""Query executor.

Executes query plans by orchestrating SDK service calls.
This module is CLI-only and NOT part of the public SDK API.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from .aggregates import apply_having, compute_aggregates, group_and_aggregate
from .exceptions import (
    QueryExecutionError,
    QueryInterruptedError,
    QuerySafetyLimitError,
    QueryTimeoutError,
)
from .filters import compile_filter, resolve_field_path
from .models import ExecutionPlan, PlanStep, Query, QueryResult
from .schema import SCHEMA_REGISTRY, get_relationship

if TYPE_CHECKING:
    from affinity import AsyncAffinity
    from affinity.models.pagination import PaginationProgress


# =============================================================================
# Progress Callback Protocol
# =============================================================================


class QueryProgressCallback(Protocol):
    """Protocol for query execution progress callbacks."""

    def on_step_start(self, step: PlanStep) -> None:
        """Called when a step starts."""
        ...

    def on_step_progress(self, step: PlanStep, current: int, total: int | None) -> None:
        """Called during step execution with progress update."""
        ...

    def on_step_complete(self, step: PlanStep, records: int) -> None:
        """Called when a step completes."""
        ...

    def on_step_error(self, step: PlanStep, error: Exception) -> None:
        """Called when a step fails."""
        ...


class NullProgressCallback:
    """No-op progress callback."""

    def on_step_start(self, step: PlanStep) -> None:
        pass

    def on_step_progress(self, step: PlanStep, current: int, total: int | None) -> None:
        pass

    def on_step_complete(self, step: PlanStep, records: int) -> None:
        pass

    def on_step_error(self, step: PlanStep, error: Exception) -> None:
        pass


# =============================================================================
# Execution Context
# =============================================================================


@dataclass
class ExecutionContext:
    """Tracks state during query execution."""

    query: Query
    records: list[dict[str, Any]] = field(default_factory=list)
    included: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    relationship_counts: dict[str, dict[int, int]] = field(default_factory=dict)
    current_step: int = 0
    start_time: float = field(default_factory=time.time)
    max_records: int = 10000
    interrupted: bool = False

    def check_timeout(self, timeout: float) -> None:
        """Check if execution has exceeded timeout."""
        elapsed = time.time() - self.start_time
        if elapsed > timeout:
            raise QueryTimeoutError(
                f"Query execution exceeded timeout of {timeout}s",
                timeout_seconds=timeout,
                elapsed_seconds=elapsed,
                partial_results=self.records,
            )

    def check_max_records(self) -> None:
        """Check if max records limit has been reached."""
        if len(self.records) >= self.max_records:
            raise QuerySafetyLimitError(
                f"Query would exceed maximum of {self.max_records} records",
                limit_name="max_records",
                limit_value=self.max_records,
                estimated_value=len(self.records),
            )

    def build_result(self) -> QueryResult:
        """Build final query result."""
        return QueryResult(
            data=self.records,
            included=self.included,
            meta={
                "recordCount": len(self.records),
                "executionTime": time.time() - self.start_time,
                "interrupted": self.interrupted,
            },
        )


# =============================================================================
# Query Executor
# =============================================================================


class QueryExecutor:
    """Executes query plans using SDK services.

    This class orchestrates SDK service calls to execute structured queries.
    It is CLI-specific and NOT part of the public SDK API.
    """

    def __init__(
        self,
        client: AsyncAffinity,
        *,
        progress: QueryProgressCallback | None = None,
        concurrency: int = 10,
        max_records: int = 10000,
        timeout: float = 300.0,
        allow_partial: bool = False,
    ) -> None:
        """Initialize the executor.

        Args:
            client: AsyncAffinity client for API calls
            progress: Optional progress callback
            concurrency: Max concurrent API calls for N+1 operations
            max_records: Safety limit on total records
            timeout: Total execution timeout in seconds
            allow_partial: If True, return partial results on interruption
        """
        self.client = client
        self.progress = progress or NullProgressCallback()
        self.concurrency = concurrency
        self.max_records = max_records
        self.timeout = timeout
        self.allow_partial = allow_partial
        self.semaphore = asyncio.Semaphore(concurrency)

    async def execute(self, plan: ExecutionPlan) -> QueryResult:
        """Execute a query plan.

        Args:
            plan: The execution plan to run

        Returns:
            QueryResult with data and included records

        Raises:
            QueryExecutionError: If execution fails
            QueryInterruptedError: If interrupted (Ctrl+C)
            QueryTimeoutError: If timeout exceeded
            QuerySafetyLimitError: If max_records exceeded
        """
        ctx = ExecutionContext(
            query=plan.query,
            max_records=self.max_records,
        )

        try:
            # Verify auth before starting
            await self._verify_auth()

            # Execute steps in dependency order
            for step in plan.steps:
                ctx.current_step = step.step_id
                ctx.check_timeout(self.timeout)

                self.progress.on_step_start(step)

                try:
                    await self._execute_step(step, ctx)
                    self.progress.on_step_complete(step, len(ctx.records))
                except Exception as e:
                    self.progress.on_step_error(step, e)
                    raise

            return ctx.build_result()

        except KeyboardInterrupt:
            ctx.interrupted = True
            if self.allow_partial and ctx.records:
                return ctx.build_result()
            raise QueryInterruptedError(
                f"Query interrupted at step {ctx.current_step}. "
                f"{len(ctx.records)} records fetched before interruption.",
                step_id=ctx.current_step,
                records_fetched=len(ctx.records),
                partial_results=ctx.records,
            ) from None

    async def _verify_auth(self) -> None:
        """Verify client is authenticated."""
        try:
            await self.client.whoami()
        except Exception as e:
            raise QueryExecutionError(
                "Authentication failed. Check your API key before running queries.",
                cause=e,
            ) from None

    async def _execute_step(self, step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute a single plan step."""
        if step.operation == "fetch":
            await self._execute_fetch(step, ctx)
        elif step.operation == "filter":
            self._execute_filter(step, ctx)
        elif step.operation == "include":
            await self._execute_include(step, ctx)
        elif step.operation == "aggregate":
            self._execute_aggregate(step, ctx)
        elif step.operation == "sort":
            self._execute_sort(step, ctx)
        elif step.operation == "limit":
            self._execute_limit(step, ctx)

    async def _execute_fetch(self, step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute a fetch step."""
        if step.entity is None:
            raise QueryExecutionError("Fetch step missing entity", step=step)

        schema = SCHEMA_REGISTRY.get(step.entity)
        if schema is None:
            raise QueryExecutionError(f"Unknown entity: {step.entity}", step=step)

        # Use page-level iteration for progress
        items_fetched = 0

        def on_progress(p: PaginationProgress) -> None:
            nonlocal items_fetched
            items_fetched = p.items_so_far
            self.progress.on_step_progress(step, items_fetched, None)

        try:
            # Special handling for listEntries - requires listId filter
            if step.entity == "listEntries":
                await self._fetch_list_entries(step, ctx)
            else:
                service = getattr(self.client, schema.service_attr)
                async for page in service.all().pages(on_progress=on_progress):
                    for record in page.data:
                        record_dict = record.model_dump(mode="json", by_alias=True)
                        ctx.records.append(record_dict)

                        # Check limits
                        if len(ctx.records) >= ctx.max_records:
                            return
                        if ctx.query.limit and len(ctx.records) >= ctx.query.limit:
                            return
        except QueryExecutionError:
            raise
        except Exception as e:
            raise QueryExecutionError(
                f"Failed to fetch {step.entity}: {e}",
                step=step,
                cause=e,
                partial_results=ctx.records,
            ) from None

    async def _fetch_list_entries(
        self,
        step: PlanStep,
        ctx: ExecutionContext,
    ) -> None:
        """Fetch list entries for a specific list.

        List entries are always scoped to a list, so this requires
        a listId filter in the where clause.
        """
        from affinity.types import ListId

        # Extract listId from where clause
        list_id = self._extract_list_id_from_where(ctx.query.where)
        if list_id is None:
            raise QueryExecutionError(
                "Query for 'listEntries' requires a 'listId' filter. "
                "Example: "
                '{"from": "listEntries", "where": {"path": "listId", "op": "eq", "value": 12345}}',
                step=step,
            )

        # Get list entry service for this specific list
        entry_service = self.client.lists.entries(ListId(list_id))

        # List entries use AsyncIterator, not paginator with .pages()
        items_fetched = 0
        async for record in entry_service.all():
            record_dict = record.model_dump(mode="json", by_alias=True)
            ctx.records.append(record_dict)
            items_fetched += 1

            # Report progress periodically
            if items_fetched % 100 == 0:
                self.progress.on_step_progress(step, items_fetched, None)

            # Check limits
            if len(ctx.records) >= ctx.max_records:
                return
            if ctx.query.limit and len(ctx.records) >= ctx.query.limit:
                return

    def _extract_list_id_from_where(self, where: Any) -> int | None:
        """Extract listId value from where clause.

        Supports formats:
        - {"path": "listId", "op": "eq", "value": 12345}
        - {"and": [{"path": "listId", "op": "eq", "value": 12345}, ...]}
        """
        if where is None:
            return None

        # Handle WhereClause model
        if hasattr(where, "model_dump"):
            where = where.model_dump(mode="json")

        if not isinstance(where, dict):
            return None

        # Check path/op/value format (the standard where clause format)
        path = where.get("path")
        op = where.get("op")
        value = where.get("value")
        if path == "listId" and op == "eq" and isinstance(value, int):
            return value

        # Check in "and" conditions
        if "and" in where:
            for condition in where["and"]:
                result = self._extract_list_id_from_where(condition)
                if result is not None:
                    return result

        return None

    def _execute_filter(self, _step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute a client-side filter step."""
        where = ctx.query.where
        if where is None:
            return

        filter_func = compile_filter(where)
        ctx.records = [r for r in ctx.records if filter_func(r)]

    async def _execute_include(self, step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute an include step (N+1 fetching)."""
        if step.relationship is None or step.entity is None:
            return

        rel = get_relationship(step.entity, step.relationship)
        if rel is None:
            raise QueryExecutionError(
                f"Unknown relationship: {step.entity}.{step.relationship}",
                step=step,
            )

        included_records: list[dict[str, Any]] = []

        if rel.fetch_strategy == "entity_method":
            # N+1: fetch for each record
            async def fetch_one(record: dict[str, Any]) -> list[dict[str, Any]]:
                async with self.semaphore:
                    entity_id = record.get("id")
                    if entity_id is None:
                        return []

                    service = getattr(self.client, step.entity or "")
                    method = getattr(service, rel.method_or_service, None)
                    if method is None:
                        return []

                    try:
                        ids = await method(entity_id)
                        # If we got IDs, we need to fetch the full records
                        # For now, just store the IDs
                        return [{"id": id_} for id_ in ids]
                    except Exception:
                        return []

            # Execute in parallel with bounded concurrency
            tasks = [fetch_one(r) for r in ctx.records]
            results = await asyncio.gather(*tasks)

            for result in results:
                included_records.extend(result)

        elif rel.fetch_strategy == "global_service":
            # Single filtered call per entity type
            # This is more efficient than N+1
            service = getattr(self.client, rel.method_or_service)

            # Collect all entity IDs
            entity_ids = [r.get("id") for r in ctx.records if r.get("id") is not None]

            for entity_id in entity_ids:
                try:
                    filter_kwargs = {rel.filter_field: entity_id}
                    response = await service.list(**filter_kwargs)
                    for item in response.data:
                        included_records.append(item.model_dump(mode="json"))
                except Exception:
                    continue

        ctx.included[step.relationship] = included_records

        # Update progress
        self.progress.on_step_progress(step, len(included_records), None)

    def _execute_aggregate(self, _step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute aggregation step."""
        if ctx.query.aggregate is None:
            return

        if ctx.query.group_by is not None:
            # Group and aggregate
            results = group_and_aggregate(
                ctx.records,
                ctx.query.group_by,
                ctx.query.aggregate,
            )

            # Apply having if present
            if ctx.query.having is not None:
                results = apply_having(results, ctx.query.having)

            ctx.records = results
        else:
            # Simple aggregate (single result)
            agg_result = compute_aggregates(ctx.records, ctx.query.aggregate)
            ctx.records = [agg_result]

    def _execute_sort(self, _step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute sort step."""
        order_by = ctx.query.order_by
        if order_by is None:
            return

        # Build sort key function
        def sort_key(record: dict[str, Any]) -> tuple[Any, ...]:
            keys: list[Any] = []
            for order in order_by:
                value = resolve_field_path(record, order.field) if order.field else None

                # Handle None values (sort to end)
                if value is None:
                    if order.direction == "asc":
                        keys.append((1, None))
                    else:
                        keys.append((0, None))
                elif order.direction == "asc":
                    keys.append((0, value))
                else:
                    # Negate for desc, but handle non-numeric
                    try:
                        keys.append((0, -value))
                    except TypeError:
                        keys.append((0, value))

            return tuple(keys)

        # Sort with stable algorithm
        try:
            ctx.records.sort(key=sort_key)
        except TypeError:
            # Mixed types - fall back to string comparison
            for order in reversed(order_by):
                reverse = order.direction == "desc"
                field = order.field or ""

                def make_key(f: str) -> Callable[[dict[str, Any]], str]:
                    return lambda r: str(resolve_field_path(r, f) or "")

                ctx.records.sort(key=make_key(field), reverse=reverse)

    def _execute_limit(self, _step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute limit step."""
        if ctx.query.limit is not None:
            ctx.records = ctx.records[: ctx.query.limit]


# =============================================================================
# Convenience Function
# =============================================================================


async def execute_query(
    client: AsyncAffinity,
    plan: ExecutionPlan,
    *,
    progress: QueryProgressCallback | None = None,
    concurrency: int = 10,
    max_records: int = 10000,
    timeout: float = 300.0,
) -> QueryResult:
    """Execute a query plan.

    Convenience function that creates an executor and runs the plan.

    Args:
        client: AsyncAffinity client
        plan: Execution plan
        progress: Optional progress callback
        concurrency: Max concurrent API calls
        max_records: Safety limit
        timeout: Execution timeout

    Returns:
        QueryResult
    """
    executor = QueryExecutor(
        client,
        progress=progress,
        concurrency=concurrency,
        max_records=max_records,
        timeout=timeout,
    )
    return await executor.execute(plan)
