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
from .schema import SCHEMA_REGISTRY, FetchStrategy, get_relationship

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
    resolved_where: dict[str, Any] | None = None  # Where clause with resolved names

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
        """Execute a fetch step.

        Routes to appropriate fetch strategy based on schema configuration.
        """
        if step.entity is None:
            raise QueryExecutionError("Fetch step missing entity", step=step)

        schema = SCHEMA_REGISTRY.get(step.entity)
        if schema is None:
            raise QueryExecutionError(f"Unknown entity: {step.entity}", step=step)

        try:
            match schema.fetch_strategy:
                case FetchStrategy.GLOBAL:
                    await self._fetch_global(step, ctx, schema)
                case FetchStrategy.REQUIRES_PARENT:
                    await self._fetch_with_parent(step, ctx, schema)
                case FetchStrategy.RELATIONSHIP_ONLY:
                    # Should never reach here - parser rejects these
                    raise QueryExecutionError(
                        f"'{step.entity}' cannot be queried directly. "
                        "This should have been caught at parse time.",
                        step=step,
                    )
        except QueryExecutionError:
            raise
        except Exception as e:
            raise QueryExecutionError(
                f"Failed to fetch {step.entity}: {e}",
                step=step,
                cause=e,
                partial_results=ctx.records,
            ) from None

    async def _fetch_global(
        self,
        step: PlanStep,
        ctx: ExecutionContext,
        schema: Any,
    ) -> None:
        """Fetch entities that support global iteration (service.all())."""
        service = getattr(self.client, schema.service_attr)

        def on_progress(p: PaginationProgress) -> None:
            self.progress.on_step_progress(step, p.items_so_far, None)

        async for page in service.all().pages(on_progress=on_progress):
            for record in page.data:
                record_dict = record.model_dump(mode="json", by_alias=True)
                ctx.records.append(record_dict)

                if self._should_stop(ctx):
                    return

    async def _fetch_with_parent(
        self,
        step: PlanStep,
        ctx: ExecutionContext,
        schema: Any,
    ) -> None:
        """Fetch entities that require a parent ID filter.

        Uses schema configuration to determine:
        - Which field to extract from the where clause (parent_filter_field)
        - What type to cast the ID to (parent_id_type)
        - Which method to call on the parent service (parent_method_name)

        Supports OR/IN conditions by extracting ALL parent IDs and fetching from each
        in parallel, merging results.
        """
        # Resolve name-based lookups BEFORE extracting parent IDs
        where = ctx.query.where
        if where is not None:
            # Convert WhereClause to dict for resolution
            where_as_dict: dict[str, Any] = (
                where.model_dump(mode="json") if hasattr(where, "model_dump") else where  # type: ignore[assignment]
            )
            where_dict = await self._resolve_list_names_to_ids(where_as_dict)
        else:
            where_dict = None

        # Extract ALL parent IDs from where clause (supports OR/IN conditions)
        parent_ids = self._extract_parent_ids(where_dict, schema.parent_filter_field)

        # Resolve field names to IDs for listEntries queries (after we know parent IDs)
        if where_dict is not None and parent_ids:
            where_dict = await self._resolve_field_names_to_ids(where_dict, parent_ids)
            # Store resolved where for use in filtering step
            ctx.resolved_where = where_dict
        if not parent_ids:
            # Should never happen - parser validates this
            raise QueryExecutionError(
                f"Query for '{step.entity}' requires a '{schema.parent_filter_field}' filter.",
                step=step,
            )

        # Get the parent service (e.g., client.lists)
        parent_service = getattr(self.client, schema.service_attr)

        # Cast all IDs to typed IDs if configured
        if schema.parent_id_type:
            from affinity import types as affinity_types

            id_type = getattr(affinity_types, schema.parent_id_type)
            parent_ids = [id_type(pid) for pid in parent_ids]

        nested_method = getattr(parent_service, schema.parent_method_name)

        # For single parent ID, use simple sequential fetch
        if len(parent_ids) == 1:
            await self._fetch_from_single_parent(step, ctx, nested_method, parent_ids[0])
            return

        # For multiple parent IDs, fetch in parallel
        async def fetch_from_parent(parent_id: Any) -> list[dict[str, Any]]:
            """Fetch all records from a single parent."""
            nested_service = nested_method(parent_id)
            results: list[dict[str, Any]] = []

            # Try paginated iteration first
            if hasattr(nested_service.all(), "pages"):
                async for page in nested_service.all().pages():
                    for record in page.data:
                        results.append(record.model_dump(mode="json", by_alias=True))
            else:
                async for record in nested_service.all():
                    results.append(record.model_dump(mode="json", by_alias=True))

            return results

        # Execute all fetches in parallel
        all_results = await asyncio.gather(*[fetch_from_parent(pid) for pid in parent_ids])

        # Merge results, respecting limits
        for results in all_results:
            for record_dict in results:
                ctx.records.append(record_dict)
                if self._should_stop(ctx):
                    return

            # Report progress after each parent completes
            self.progress.on_step_progress(step, len(ctx.records), None)

    async def _fetch_from_single_parent(
        self,
        step: PlanStep,
        ctx: ExecutionContext,
        nested_method: Callable[..., Any],
        parent_id: Any,
    ) -> None:
        """Fetch from a single parent with progress reporting."""
        nested_service = nested_method(parent_id)
        items_fetched = 0

        def on_progress(p: PaginationProgress) -> None:
            nonlocal items_fetched
            items_fetched = p.items_so_far
            self.progress.on_step_progress(step, items_fetched, None)

        # Try paginated iteration first (consistent with _fetch_global)
        if hasattr(nested_service.all(), "pages"):
            async for page in nested_service.all().pages(on_progress=on_progress):
                for record in page.data:
                    record_dict = record.model_dump(mode="json", by_alias=True)
                    ctx.records.append(record_dict)
                    if self._should_stop(ctx):
                        return
        else:
            # Fall back to async iteration for services without .pages()
            async for record in nested_service.all():
                record_dict = record.model_dump(mode="json", by_alias=True)
                ctx.records.append(record_dict)
                items_fetched += 1

                if items_fetched % 100 == 0:
                    self.progress.on_step_progress(step, items_fetched, None)

                if self._should_stop(ctx):
                    return

    def _should_stop(self, ctx: ExecutionContext) -> bool:
        """Check if we should stop fetching."""
        if len(ctx.records) >= ctx.max_records:
            return True
        return bool(ctx.query.limit and len(ctx.records) >= ctx.query.limit)

    def _extract_parent_ids(self, where: Any, field_name: str | None) -> list[int]:
        """Extract ALL parent ID values from where clause.

        Handles all condition types:
        - Direct eq: {"path": "listId", "op": "eq", "value": 12345}
        - Direct eq (string): {"path": "listId", "op": "eq", "value": "12345"}
        - Direct in: {"path": "listId", "op": "in", "value": [123, 456, 789]}
        - AND: {"and": [{"path": "listId", "op": "eq", "value": 123}, ...]}
        - OR: {"or": [{"path": "listId", "op": "eq", "value": 123},
                      {"path": "listId", "op": "eq", "value": 456}]}

        Accepts both integer and string IDs (strings are converted to int).
        Returns deduplicated list of all parent IDs found.
        """
        if where is None or field_name is None:
            return []

        if hasattr(where, "model_dump"):
            where = where.model_dump(mode="json")

        if not isinstance(where, dict):
            return []

        def to_int(value: Any) -> int | None:
            """Convert value to int, supporting both int and numeric strings."""
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    return None
            return None

        ids: list[int] = []

        # Direct condition with "eq" operator
        if where.get("path") == field_name and where.get("op") == "eq":
            value = where.get("value")
            int_val = to_int(value)
            if int_val is not None:
                ids.append(int_val)

        # Direct condition with "in" operator (list of IDs)
        if where.get("path") == field_name and where.get("op") == "in":
            value = where.get("value")
            if isinstance(value, list):
                for v in value:
                    int_val = to_int(v)
                    if int_val is not None:
                        ids.append(int_val)

        # Compound "and" conditions - traverse recursively
        if "and" in where:
            for condition in where["and"]:
                ids.extend(self._extract_parent_ids(condition, field_name))

        # Compound "or" conditions - traverse recursively
        if "or" in where:
            for condition in where["or"]:
                ids.extend(self._extract_parent_ids(condition, field_name))

        # NOTE: "not" clauses are intentionally NOT traversed.
        # Negated parent filters are rejected by the parser.

        # Deduplicate while preserving order
        seen: set[int] = set()
        unique_ids: list[int] = []
        for id_ in ids:
            if id_ not in seen:
                seen.add(id_)
                unique_ids.append(id_)

        return unique_ids

    async def _resolve_list_names_to_ids(self, where: dict[str, Any]) -> dict[str, Any]:
        """Resolve listName references to listId.

        Transforms:
            {"path": "listName", "op": "eq", "value": "My Deals"}
        Into:
            {"path": "listId", "op": "eq", "value": 12345}

        Also handles:
            {"path": "listName", "op": "in", "value": ["Deals", "Leads"]}

        Cache behavior: The list name cache is populated once per QueryExecutor
        instance. Since QueryExecutor is created fresh for each execute() call,
        the cache is effectively per-query.
        """
        if not isinstance(where, dict):
            return where

        # Check if this is a listName condition
        if where.get("path") == "listName":
            names = where.get("value")
            op = where.get("op")

            # Fetch all lists once and cache
            if not hasattr(self, "_list_name_cache"):
                self._list_name_cache: dict[str, int] = {}
                async for list_obj in self.client.lists.all():
                    self._list_name_cache[list_obj.name] = list_obj.id

            if op == "eq" and isinstance(names, str):
                list_id = self._list_name_cache.get(names)
                if list_id is None:
                    raise QueryExecutionError(f"List not found: '{names}'")
                return {"path": "listId", "op": "eq", "value": list_id}

            if op == "in" and isinstance(names, list):
                list_ids = []
                for name in names:
                    list_id = self._list_name_cache.get(name)
                    if list_id is None:
                        raise QueryExecutionError(f"List not found: '{name}'")
                    list_ids.append(list_id)
                return {"path": "listId", "op": "in", "value": list_ids}

        # Recursively process compound conditions
        result = dict(where)
        if "and" in where:
            result["and"] = [await self._resolve_list_names_to_ids(c) for c in where["and"]]
        if "or" in where:
            result["or"] = [await self._resolve_list_names_to_ids(c) for c in where["or"]]

        return result

    async def _resolve_field_names_to_ids(
        self, where: dict[str, Any], list_ids: list[int]
    ) -> dict[str, Any]:
        """Resolve field name references to field IDs in fields.* paths.

        Transforms:
            {"path": "fields.Status", "op": "eq", "value": "Active"}
        Into:
            {"path": "fields.12345", "op": "eq", "value": "Active"}

        Field names are resolved case-insensitively against the field definitions
        for the specified list(s).

        Args:
            where: The where clause to transform
            list_ids: List IDs to fetch field metadata from

        Returns:
            Transformed where clause with field names resolved to IDs
        """
        if not isinstance(where, dict) or not list_ids:
            return where

        # Build field name cache for all lists
        if not hasattr(self, "_field_name_cache"):
            self._field_name_cache: dict[str, str] = {}

            from affinity.types import ListId

            for list_id in list_ids:
                try:
                    fields = await self.client.lists.get_fields(ListId(list_id))
                    for field in fields:
                        if field.name:
                            # Map lowercase name to field ID
                            self._field_name_cache[field.name.lower()] = str(field.id)
                except Exception:
                    # If we can't fetch fields, continue without resolution
                    pass

        # Check if this is a fields.* condition
        path = where.get("path", "")
        if isinstance(path, str) and path.startswith("fields."):
            field_ref = path[7:]  # Everything after "fields."

            # Skip if already a field ID (numeric or "field-" prefix)
            if not field_ref.isdigit() and not field_ref.startswith("field-"):
                # Try to resolve by name (case-insensitive)
                field_id = self._field_name_cache.get(field_ref.lower())
                if field_id is not None:
                    result = dict(where)
                    result["path"] = f"fields.{field_id}"
                    return result

        # Recursively process compound conditions
        result = dict(where)
        if "and" in where:
            result["and"] = [
                await self._resolve_field_names_to_ids(c, list_ids) for c in where["and"]
            ]
        if "or" in where:
            result["or"] = [
                await self._resolve_field_names_to_ids(c, list_ids) for c in where["or"]
            ]

        return result

    def _execute_filter(self, _step: PlanStep, ctx: ExecutionContext) -> None:
        """Execute a client-side filter step."""
        from .models import WhereClause as WC

        # Use resolved where clause if available (has field names → IDs resolved)
        where: WC | None
        if ctx.resolved_where is not None:
            # Convert dict back to WhereClause for compile_filter
            where = WC.model_validate(ctx.resolved_where)
        else:
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
