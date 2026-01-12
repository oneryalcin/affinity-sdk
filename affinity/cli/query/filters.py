"""Filter operators for query WHERE clauses.

This module provides extended filter operators beyond what the SDK supports.
It is CLI-only and NOT part of the public SDK API.

Uses the shared compare module (affinity/compare.py) for comparison logic,
ensuring consistent behavior between SDK filter and Query tool.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...compare import compare_values
from .dates import parse_date_value
from .exceptions import QueryValidationError
from .models import WhereClause

# =============================================================================
# Operator Definitions
# =============================================================================

# Type alias for operator functions
OperatorFunc = Callable[[Any, Any], bool]


def _make_operator(op_name: str) -> OperatorFunc:
    """Create an operator function that delegates to compare_values().

    This is a factory function that creates operator functions for the OPERATORS
    registry. Each function wraps compare_values() with the appropriate operator name.
    """

    def op_func(field_value: Any, target: Any) -> bool:
        return compare_values(field_value, target, op_name)

    return op_func


# Operator registry - all operators delegate to compare_values() from the shared module
# This ensures consistent comparison behavior between SDK filter and Query tool
OPERATORS: dict[str, OperatorFunc] = {
    "eq": _make_operator("eq"),
    "neq": _make_operator("neq"),
    "gt": _make_operator("gt"),
    "gte": _make_operator("gte"),
    "lt": _make_operator("lt"),
    "lte": _make_operator("lte"),
    "contains": _make_operator("contains"),
    "starts_with": _make_operator("starts_with"),
    "ends_with": _make_operator("ends_with"),  # New: was missing in query tool
    "in": _make_operator("in"),
    "between": _make_operator("between"),
    "is_null": _make_operator("is_null"),
    "is_not_null": _make_operator("is_not_null"),
    "is_empty": _make_operator("is_empty"),  # New: was missing in query tool
    "contains_any": _make_operator("contains_any"),
    "contains_all": _make_operator("contains_all"),
    "has_any": _make_operator("has_any"),
    "has_all": _make_operator("has_all"),
}


# =============================================================================
# Field Path Resolution
# =============================================================================


def resolve_field_path(record: dict[str, Any], path: str) -> Any:
    """Resolve a field path to a value.

    Supports:
    - Simple fields: "firstName"
    - Nested fields: "address.city"
    - Array fields: "emails[0]"
    - Special fields: "fields.Status" for list entry fields

    Args:
        record: The record to extract value from
        path: The field path

    Returns:
        The resolved value, or None if not found
    """
    if not path:
        return None

    parts = _parse_field_path(path)
    current: Any = record

    for part in parts:
        if current is None:
            return None

        if isinstance(part, int):
            # Array index
            if isinstance(current, list) and 0 <= part < len(current):
                current = current[part]
            else:
                return None
        elif isinstance(current, dict):
            # Object property
            current = current.get(part)
        else:
            return None

    return current


def _parse_field_path(path: str) -> list[str | int]:
    """Parse a field path into parts.

    Examples:
        "firstName" -> ["firstName"]
        "address.city" -> ["address", "city"]
        "emails[0]" -> ["emails", 0]
        "fields.Status" -> ["fields", "Status"]
    """
    parts: list[str | int] = []
    current = ""
    i = 0

    while i < len(path):
        char = path[i]

        if char == ".":
            if current:
                parts.append(current)
                current = ""
            i += 1
        elif char == "[":
            if current:
                parts.append(current)
                current = ""
            # Find closing bracket
            end = path.find("]", i)
            if end == -1:
                raise QueryValidationError(f"Unclosed bracket in field path: {path}")
            index_str = path[i + 1 : end]
            try:
                parts.append(int(index_str))
            except ValueError:
                # Non-numeric index, treat as string
                parts.append(index_str)
            i = end + 1
        else:
            current += char
            i += 1

    if current:
        parts.append(current)

    return parts


# =============================================================================
# Filter Compilation
# =============================================================================


def compile_filter(where: WhereClause) -> Callable[[dict[str, Any]], bool]:
    """Compile a WHERE clause into a filter function.

    Args:
        where: The WHERE clause to compile

    Returns:
        A function that takes a record and returns True if it matches
    """
    # Single condition
    if where.op is not None:
        return _compile_condition(where)

    # Compound conditions
    if where.and_ is not None:
        filters = [compile_filter(clause) for clause in where.and_]
        return lambda record: all(f(record) for f in filters)

    if where.or_ is not None:
        filters = [compile_filter(clause) for clause in where.or_]
        return lambda record: any(f(record) for f in filters)

    if where.not_ is not None:
        inner = compile_filter(where.not_)
        return lambda record: not inner(record)

    # Quantifiers (all, none) - placeholder, requires relationship fetching
    if where.all_ is not None or where.none_ is not None:
        # These require relationship data and are handled by executor
        # For now, pass through
        return lambda _: True

    # Exists - placeholder, requires subquery execution
    if where.exists_ is not None:
        return lambda _: True

    # No conditions - match all
    return lambda _: True


def _compile_condition(where: WhereClause) -> Callable[[dict[str, Any]], bool]:
    """Compile a single filter condition."""
    if where.op is None:
        return lambda _: True

    op_func = OPERATORS.get(where.op)
    if op_func is None:
        raise QueryValidationError(f"Unknown operator: {where.op}")

    path = where.path
    value = where.value

    # Parse date values if they look like relative dates
    if value is not None and isinstance(value, str):
        parsed_value = parse_date_value(value)
        if parsed_value is not None:
            value = parsed_value

    # Handle _count pseudo-field
    if path and path.endswith("._count"):
        # This requires relationship counting, handled by executor
        # Return a placeholder that always matches
        return lambda _: True

    def filter_func(record: dict[str, Any]) -> bool:
        if path is None:
            return True
        field_value = resolve_field_path(record, path)
        return op_func(field_value, value)

    return filter_func


def matches(record: dict[str, Any], where: WhereClause | None) -> bool:
    """Check if a record matches a WHERE clause.

    Args:
        record: The record to check
        where: The WHERE clause, or None (matches all)

    Returns:
        True if the record matches
    """
    if where is None:
        return True
    filter_func = compile_filter(where)
    return filter_func(record)
