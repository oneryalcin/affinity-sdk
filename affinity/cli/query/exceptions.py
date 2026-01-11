"""Query engine exceptions.

These exceptions are specific to the query engine and are CLI-only.
They are NOT part of the public SDK API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import PlanStep


class QueryError(Exception):
    """Base class for query engine errors."""

    pass


class QueryParseError(QueryError):
    """Raised when query parsing or validation fails.

    Examples:
        - Invalid JSON syntax
        - Unknown operator
        - Invalid field path
        - Type mismatch in value
        - Unsupported query version
    """

    def __init__(self, message: str, *, field: str | None = None) -> None:
        self.field = field
        if field:
            message = f"{field}: {message}"
        super().__init__(message)


class QueryValidationError(QueryError):
    """Raised when query passes parsing but fails semantic validation.

    Examples:
        - Aggregate with include (not allowed)
        - Unknown entity type
        - Invalid relationship path
        - groupBy with incompatible aggregate
    """

    def __init__(self, message: str, *, field: str | None = None) -> None:
        self.field = field
        if field:
            message = f"{field}: {message}"
        super().__init__(message)


class QueryPlanError(QueryError):
    """Raised when execution plan cannot be generated.

    Examples:
        - Circular dependency in plan steps
        - Unknown entity in schema registry
    """

    pass


class QueryExecutionError(QueryError):
    """Raised during query execution.

    Examples:
        - API call failed
        - Authentication error
        - Rate limiting exhausted
        - Timeout exceeded
    """

    def __init__(
        self,
        message: str,
        *,
        step: PlanStep | None = None,
        cause: Exception | None = None,
        partial_results: list[Any] | None = None,
    ) -> None:
        self.step = step
        self.cause = cause
        self.partial_results = partial_results
        super().__init__(message)


class QueryInterruptedError(QueryError):
    """Raised when query execution is interrupted (e.g., Ctrl+C).

    Carries partial results that were collected before interruption.
    """

    def __init__(
        self,
        message: str,
        *,
        step_id: int | None = None,
        records_fetched: int = 0,
        partial_results: list[Any] | None = None,
    ) -> None:
        self.step_id = step_id
        self.records_fetched = records_fetched
        self.partial_results = partial_results
        super().__init__(message)


class QueryTimeoutError(QueryExecutionError):
    """Raised when query execution exceeds the timeout."""

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: float,
        elapsed_seconds: float,
        step: PlanStep | None = None,
        partial_results: list[Any] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds
        super().__init__(message, step=step, partial_results=partial_results)


class QuerySafetyLimitError(QueryError):
    """Raised when query would exceed safety limits.

    Examples:
        - Estimated records > max_records
        - Estimated API calls > threshold
    """

    def __init__(
        self,
        message: str,
        *,
        limit_name: str,
        limit_value: int,
        estimated_value: int,
    ) -> None:
        self.limit_name = limit_name
        self.limit_value = limit_value
        self.estimated_value = estimated_value
        super().__init__(message)
