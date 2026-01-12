"""Filter operators for query WHERE clauses.

This module provides extended filter operators beyond what the SDK supports.
It is CLI-only and NOT part of the public SDK API.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .dates import parse_date_value
from .exceptions import QueryValidationError
from .models import WhereClause

# =============================================================================
# Operator Definitions
# =============================================================================

# Type alias for operator functions
OperatorFunc = Callable[[Any, Any], bool]


def _safe_compare(a: Any, b: Any, op: Callable[[Any, Any], bool]) -> bool:
    """Safely compare values, handling None and type mismatches."""
    if a is None or b is None:
        return False
    try:
        return op(a, b)
    except TypeError:
        # Type mismatch - try string comparison
        return op(str(a), str(b))


def _eq(a: Any, b: Any) -> bool:
    """Equality operator with array membership support.

    For scalar fields: standard equality (a == b)
    For array fields (multi-select dropdowns):
      - eq with scalar: checks if scalar is IN the array (membership)
      - eq with array: checks set equality (order-insensitive, same elements)

    This semantic shift is intentional - the query engine does client-side
    filtering without field-type knowledge, so eq needs to "do the right thing"
    for both single-value and multi-select fields.
    """
    if a is None:
        return b is None
    # If field value is a list, check if filter value is IN the list
    if isinstance(a, list):
        # If comparing list to list, check set equality (order-insensitive)
        if isinstance(b, list):
            try:
                return set(a) == set(b)
            except TypeError:
                # Unhashable elements - fall back to sorted comparison
                try:
                    return sorted(a) == sorted(b)
                except TypeError:
                    return a == b  # Last resort: order-sensitive equality
        return b in a
    return bool(a == b)


def _neq(a: Any, b: Any) -> bool:
    """Not equal operator with array membership support."""
    if a is None:
        return b is not None
    if isinstance(a, list):
        if isinstance(b, list):
            try:
                return set(a) != set(b)
            except TypeError:
                try:
                    return sorted(a) != sorted(b)
                except TypeError:
                    return a != b
        return b not in a
    return bool(a != b)


def _gt(a: Any, b: Any) -> bool:
    """Greater than operator."""
    return _safe_compare(a, b, lambda x, y: x > y)


def _gte(a: Any, b: Any) -> bool:
    """Greater than or equal operator."""
    return _safe_compare(a, b, lambda x, y: x >= y)


def _lt(a: Any, b: Any) -> bool:
    """Less than operator."""
    return _safe_compare(a, b, lambda x, y: x < y)


def _lte(a: Any, b: Any) -> bool:
    """Less than or equal operator."""
    return _safe_compare(a, b, lambda x, y: x <= y)


def _contains(a: Any, b: Any) -> bool:
    """Contains operator (case-insensitive substring match)."""
    if a is None or b is None:
        return False
    return str(b).lower() in str(a).lower()


def _starts_with(a: Any, b: Any) -> bool:
    """Starts with operator (case-insensitive)."""
    if a is None or b is None:
        return False
    return str(a).lower().startswith(str(b).lower())


def _in(a: Any, b: Any) -> bool:
    """In operator - checks if value(s) exist in filter list.

    For scalar fields: checks if field value is in filter list
    For array fields: checks if ANY element of field array is in filter list

    Use case: "Find entries where Team Member includes anyone from ['LB', 'MA']"
    """
    if a is None:
        return False
    if not isinstance(b, list):
        return False
    # If a is a list, check if ANY element of a is in b
    if isinstance(a, list):
        return any(item in b for item in a)
    return a in b


def _between(a: Any, b: Any) -> bool:
    """Between operator (inclusive range)."""
    if a is None or not isinstance(b, list) or len(b) != 2:
        return False
    try:
        return bool(b[0] <= a <= b[1])
    except TypeError:
        return False


def _is_null(a: Any, _b: Any) -> bool:
    """Is null operator."""
    return a is None


def _is_not_null(a: Any, _b: Any) -> bool:
    """Is not null operator."""
    return a is not None


def _contains_any(a: Any, b: Any) -> bool:
    """Contains any of the given terms (case-insensitive)."""
    if a is None or not isinstance(b, list):
        return False
    a_lower = str(a).lower()
    return any(str(term).lower() in a_lower for term in b)


def _contains_all(a: Any, b: Any) -> bool:
    """Contains all of the given terms (case-insensitive)."""
    if a is None or not isinstance(b, list):
        return False
    a_lower = str(a).lower()
    return all(str(term).lower() in a_lower for term in b)


def _has_any(a: Any, b: Any) -> bool:
    """Check if array field contains ANY of the specified elements.

    Unlike contains_any (which does case-insensitive substring matching),
    this does exact array membership checking.
    """
    if not isinstance(a, list) or not isinstance(b, list):
        return False
    if not b:  # Empty filter list = no match
        return False
    return any(elem in a for elem in b)


def _has_all(a: Any, b: Any) -> bool:
    """Check if array field contains ALL of the specified elements.

    Unlike contains_all (which does case-insensitive substring matching),
    this does exact array membership checking.
    """
    if not isinstance(a, list) or not isinstance(b, list):
        return False
    if not b:  # Empty filter list = no match (avoid vacuous truth)
        return False
    return all(elem in a for elem in b)


# Operator registry
OPERATORS: dict[str, OperatorFunc] = {
    "eq": _eq,
    "neq": _neq,
    "gt": _gt,
    "gte": _gte,
    "lt": _lt,
    "lte": _lte,
    "contains": _contains,
    "starts_with": _starts_with,
    "in": _in,
    "between": _between,
    "is_null": _is_null,
    "is_not_null": _is_not_null,
    "contains_any": _contains_any,
    "contains_all": _contains_all,
    "has_any": _has_any,
    "has_all": _has_all,
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
