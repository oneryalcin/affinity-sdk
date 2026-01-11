"""Query parser and validator.

Parses JSON queries into validated Query objects.
This module is CLI-only and NOT part of the public SDK API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .exceptions import QueryParseError, QueryValidationError
from .models import Query, WhereClause

# =============================================================================
# Version Configuration
# =============================================================================

CURRENT_VERSION = "1.0"
SUPPORTED_VERSIONS = frozenset(["1.0"])
DEPRECATED_VERSIONS: frozenset[str] = frozenset()

# Supported operators per version
SUPPORTED_OPERATORS_V1 = frozenset(
    [
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "contains",
        "starts_with",
        "in",
        "between",
        "is_null",
        "is_not_null",
        "contains_any",
        "contains_all",
    ]
)

# Supported entities
SUPPORTED_ENTITIES = frozenset(
    [
        "persons",
        "companies",
        "opportunities",
        "listEntries",
        "interactions",
        "notes",
    ]
)


# =============================================================================
# Parse Result
# =============================================================================


class ParseResult:
    """Result of parsing a query."""

    def __init__(self, query: Query, warnings: list[str]) -> None:
        self.query = query
        self.warnings = warnings

    @property
    def version(self) -> str:
        return self.query.version or CURRENT_VERSION


# =============================================================================
# Validation Functions
# =============================================================================


def validate_version(version: str | None) -> tuple[str, list[str]]:
    """Validate and normalize query version.

    Returns:
        Tuple of (resolved_version, warnings)

    Raises:
        QueryParseError: If version is not supported
    """
    warnings: list[str] = []

    if version is None:
        warnings.append(
            "Query missing '$version' field. Assuming version 1.0. "
            'Add \'"$version": "1.0"\' for forward compatibility.'
        )
        return CURRENT_VERSION, warnings

    if version not in SUPPORTED_VERSIONS and version not in DEPRECATED_VERSIONS:
        raise QueryParseError(
            f"Unsupported query version '{version}'. "
            f"Supported versions: {', '.join(sorted(SUPPORTED_VERSIONS))}"
        )

    if version in DEPRECATED_VERSIONS:
        warnings.append(
            f"Query version '{version}' is deprecated. "
            "Run 'xaffinity query migrate --file query.json' to upgrade."
        )

    return version, warnings


def validate_entity(entity: str) -> None:
    """Validate that entity type is supported."""
    if entity not in SUPPORTED_ENTITIES:
        raise QueryValidationError(
            f"Unknown entity type '{entity}'. "
            f"Supported entities: {', '.join(sorted(SUPPORTED_ENTITIES))}",
            field="from",
        )


def validate_operator(op: str, _version: str = CURRENT_VERSION) -> None:
    """Validate that operator is supported for the given version."""
    supported = SUPPORTED_OPERATORS_V1  # Currently only v1
    if op not in supported:
        raise QueryParseError(
            f"Unknown operator '{op}'. Supported operators: {', '.join(sorted(supported))}",
            field="op",
        )


def validate_where_clause(where: WhereClause, version: str = CURRENT_VERSION) -> None:
    """Recursively validate a WHERE clause."""
    # Check for single condition
    if where.op is not None:
        validate_operator(where.op, version)

        # Validate that path or expr is provided
        if where.path is None and where.expr is None:
            raise QueryValidationError(
                "Condition must have 'path' or 'expr' field",
                field="where",
            )

        # Validate value for operators that require it
        if where.op not in ("is_null", "is_not_null") and where.value is None:
            raise QueryValidationError(
                f"Operator '{where.op}' requires a 'value' field",
                field="where",
            )

        # Validate 'between' has two-element list
        if where.op == "between" and (not isinstance(where.value, list) or len(where.value) != 2):
            raise QueryValidationError(
                "'between' operator requires a two-element array [min, max]",
                field="where.value",
            )

        # Validate 'in' has a list
        if where.op == "in" and not isinstance(where.value, list):
            raise QueryValidationError(
                "'in' operator requires an array value",
                field="where.value",
            )

    # Validate compound conditions
    if where.and_ is not None:
        for clause in where.and_:
            validate_where_clause(clause, version)

    if where.or_ is not None:
        for clause in where.or_:
            validate_where_clause(clause, version)

    if where.not_ is not None:
        validate_where_clause(where.not_, version)

    # Validate quantifiers
    if where.all_ is not None:
        validate_where_clause(where.all_.where, version)

    if where.none_ is not None:
        validate_where_clause(where.none_.where, version)

    # Validate exists
    if where.exists_ is not None:
        if where.exists_.from_ not in SUPPORTED_ENTITIES:
            raise QueryValidationError(
                f"Unknown entity type '{where.exists_.from_}' in EXISTS clause",
                field="where.exists.from",
            )
        if where.exists_.where is not None:
            validate_where_clause(where.exists_.where, version)


def validate_query_semantics(query: Query) -> list[str]:
    """Validate semantic constraints on the query.

    Returns:
        List of warnings (non-fatal issues)

    Raises:
        QueryValidationError: For fatal semantic errors
    """
    warnings: list[str] = []

    # Aggregate with include is not allowed
    if query.aggregate is not None and query.include is not None:
        raise QueryValidationError(
            "Cannot use 'aggregate' with 'include'. "
            "Aggregates collapse records, making includes meaningless.",
            field="aggregate",
        )

    # groupBy requires aggregate
    if query.group_by is not None and query.aggregate is None:
        raise QueryValidationError(
            "'groupBy' requires 'aggregate' to be specified.",
            field="groupBy",
        )

    # having requires aggregate
    if query.having is not None and query.aggregate is None:
        raise QueryValidationError(
            "'having' requires 'aggregate' to be specified.",
            field="having",
        )

    # Validate include paths
    if query.include is not None:
        for include_path in query.include:
            # Basic validation - detailed validation happens in schema.py
            if not include_path or not isinstance(include_path, str):
                raise QueryValidationError(
                    f"Invalid include path: {include_path!r}",
                    field="include",
                )

    # Validate select paths
    if query.select is not None:
        for select_path in query.select:
            if not select_path or not isinstance(select_path, str):
                raise QueryValidationError(
                    f"Invalid select path: {select_path!r}",
                    field="select",
                )

    # Validate limit
    if query.limit is not None:
        if query.limit < 0:
            raise QueryValidationError(
                "limit must be non-negative",
                field="limit",
            )
        if query.limit == 0:
            warnings.append("Query has limit=0, which will return no results.")

    return warnings


# =============================================================================
# Main Parse Function
# =============================================================================


def parse_query(
    query_input: dict[str, Any] | str,
    *,
    version_override: str | None = None,
) -> ParseResult:
    """Parse and validate a query.

    Args:
        query_input: Either a dict (already parsed JSON) or a JSON string
        version_override: If provided, overrides $version in query

    Returns:
        ParseResult with validated Query and warnings

    Raises:
        QueryParseError: For syntax/parsing errors
        QueryValidationError: For semantic validation errors
    """
    warnings: list[str] = []

    # Parse JSON if string
    if isinstance(query_input, str):
        try:
            query_dict = json.loads(query_input)
        except json.JSONDecodeError as e:
            raise QueryParseError(f"Invalid JSON: {e}") from None
    else:
        query_dict = query_input

    if not isinstance(query_dict, dict):
        raise QueryParseError("Query must be a JSON object")

    # Handle version
    version = version_override or query_dict.get("$version")
    resolved_version, version_warnings = validate_version(version)
    warnings.extend(version_warnings)

    # Set version in query dict for Pydantic
    query_dict["$version"] = resolved_version

    # Validate entity type before Pydantic parsing
    if "from" not in query_dict:
        raise QueryParseError("Query must have a 'from' field specifying the entity type")
    validate_entity(query_dict["from"])

    # Parse with Pydantic
    try:
        query = Query.model_validate(query_dict)
    except ValidationError as e:
        # Convert Pydantic errors to QueryParseError
        errors = e.errors()
        if len(errors) == 1:
            err = errors[0]
            field_path = ".".join(str(loc) for loc in err["loc"])
            raise QueryParseError(err["msg"], field=field_path) from None
        else:
            error_msgs = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in errors
            ]
            raise QueryParseError("Multiple validation errors:\n" + "\n".join(error_msgs)) from None

    # Validate WHERE clause operators
    if query.where is not None:
        validate_where_clause(query.where, resolved_version)

    # Validate semantic constraints
    semantic_warnings = validate_query_semantics(query)
    warnings.extend(semantic_warnings)

    return ParseResult(query, warnings)


def parse_query_from_file(
    filepath: str | Path, *, version_override: str | None = None
) -> ParseResult:
    """Parse a query from a file.

    Args:
        filepath: Path to JSON file
        version_override: If provided, overrides $version in query

    Returns:
        ParseResult with validated Query and warnings

    Raises:
        QueryParseError: For file read or parsing errors
    """
    path = Path(filepath) if isinstance(filepath, str) else filepath
    try:
        content = path.read_text()
    except OSError as e:
        raise QueryParseError(f"Failed to read query file: {e}") from None

    return parse_query(content, version_override=version_override)
