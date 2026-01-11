"""Query engine for the CLI.

This package provides a structured query language for querying Affinity data.
It is CLI-only and NOT part of the public SDK API.

Example:
    from affinity.cli.query import parse_query, create_planner

    result = parse_query({
        "$version": "1.0",
        "from": "persons",
        "where": {"path": "email", "op": "contains", "value": "@acme.com"},
        "limit": 50
    })

    planner = create_planner()
    plan = planner.plan(result.query)
"""

# Phase 2 modules
from .aggregates import (
    apply_having,
    compute_aggregates,
    group_and_aggregate,
)
from .dates import (
    days_since,
    days_until,
    is_relative_date,
    parse_date_value,
    parse_relative_date,
)
from .exceptions import (
    QueryError,
    QueryExecutionError,
    QueryInterruptedError,
    QueryParseError,
    QueryPlanError,
    QuerySafetyLimitError,
    QueryTimeoutError,
    QueryValidationError,
)
from .executor import (
    NullProgressCallback,
    QueryExecutor,
    QueryProgressCallback,
    execute_query,
)
from .filters import (
    compile_filter,
    matches,
    resolve_field_path,
)
from .models import (
    AggregateFunc,
    ExecutionPlan,
    FilterCondition,
    HavingClause,
    OrderByClause,
    PlanStep,
    Query,
    QueryResult,
    WhereClause,
)
from .output import (
    format_dry_run,
    format_dry_run_json,
    format_json,
    format_table,
)
from .parser import (
    CURRENT_VERSION,
    SUPPORTED_ENTITIES,
    SUPPORTED_VERSIONS,
    ParseResult,
    parse_query,
    parse_query_from_file,
)
from .planner import QueryPlanner, create_planner
from .progress import (
    NDJSONQueryProgress,
    RichQueryProgress,
    create_progress_callback,
)
from .schema import (
    SCHEMA_REGISTRY,
    EntitySchema,
    RelationshipDef,
    get_entity_relationships,
    get_entity_schema,
    get_relationship,
    get_supported_entities,
    is_valid_field_path,
)

__all__ = [
    # Exceptions
    "QueryError",
    "QueryParseError",
    "QueryValidationError",
    "QueryPlanError",
    "QueryExecutionError",
    "QueryInterruptedError",
    "QueryTimeoutError",
    "QuerySafetyLimitError",
    # Models
    "Query",
    "WhereClause",
    "FilterCondition",
    "AggregateFunc",
    "HavingClause",
    "OrderByClause",
    "PlanStep",
    "ExecutionPlan",
    "QueryResult",
    # Parser
    "parse_query",
    "parse_query_from_file",
    "ParseResult",
    "CURRENT_VERSION",
    "SUPPORTED_VERSIONS",
    "SUPPORTED_ENTITIES",
    # Planner
    "QueryPlanner",
    "create_planner",
    # Schema
    "SCHEMA_REGISTRY",
    "EntitySchema",
    "RelationshipDef",
    "get_entity_schema",
    "get_relationship",
    "get_supported_entities",
    "get_entity_relationships",
    "is_valid_field_path",
    # Filters
    "compile_filter",
    "matches",
    "resolve_field_path",
    # Dates
    "parse_relative_date",
    "parse_date_value",
    "days_since",
    "days_until",
    "is_relative_date",
    # Aggregates
    "compute_aggregates",
    "group_and_aggregate",
    "apply_having",
    # Executor
    "QueryExecutor",
    "QueryProgressCallback",
    "NullProgressCallback",
    "execute_query",
    # Output
    "format_json",
    "format_table",
    "format_dry_run",
    "format_dry_run_json",
    # Progress
    "RichQueryProgress",
    "NDJSONQueryProgress",
    "create_progress_callback",
]
