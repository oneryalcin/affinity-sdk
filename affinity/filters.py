"""
Filter builder for V2 API filtering support.

Provides a type-safe, Pythonic way to build filter expressions for V2 list endpoints.
The builder handles proper escaping and quoting of user inputs.

Example:
    from affinity.filters import Filter, F

    # Using the builder (recommended)
    filter = (
        F.field("name").contains("Acme") &
        F.field("status").equals("Active")
    )
    companies = client.companies.list(filter=filter)

    # Or build complex filters
    filter = (
        (F.field("name").contains("Corp") | F.field("name").contains("Inc")) &
        ~F.field("archived").equals(True)
    )

    # Raw filter string escape hatch (power users)
    companies = client.companies.list(filter='name =~ "Acme"')
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class RawToken:
    """
    A raw token inserted into a filter expression without quoting.

    Used for special Affinity Filtering Language literals like `*`.
    """

    token: str


def _escape_string(value: str) -> str:
    """
    Escape a string value for use in a filter expression.

    Handles:
    - Backslashes (must be doubled)
    - Double quotes (must be escaped)
    - Newlines and tabs (escaped as literals)
    - NUL bytes (removed)
    """
    # Order matters: escape backslashes first
    result = value.replace("\\", "\\\\")
    result = result.replace('"', '\\"')
    result = result.replace("\x00", "")
    result = result.replace("\n", "\\n")
    result = result.replace("\t", "\\t")
    result = result.replace("\r", "\\r")
    return result


def _format_value(value: Any) -> str:
    """Format a Python value for use in a filter expression."""
    if isinstance(value, RawToken):
        return value.token
    if value is None:
        raise ValueError("None is not a valid filter literal; use is_null()/is_not_null().")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    # Handle datetime before date (datetime is subclass of date)
    if isinstance(value, datetime):
        return f'"{value.isoformat()}"'
    if isinstance(value, date):
        return f'"{value.isoformat()}"'
    # String and fallback
    text = value if isinstance(value, str) else str(value)
    return f'"{_escape_string(text)}"'


class FilterExpression(ABC):
    """Base class for filter expressions."""

    @abstractmethod
    def to_string(self) -> str:
        """Convert the expression to a filter string."""
        ...

    def __and__(self, other: FilterExpression) -> FilterExpression:
        """Combine two expressions with `&`."""
        return AndExpression(self, other)

    def __or__(self, other: FilterExpression) -> FilterExpression:
        """Combine two expressions with `|`."""
        return OrExpression(self, other)

    def __invert__(self) -> FilterExpression:
        """Negate the expression with `!`."""
        return NotExpression(self)

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"Filter({self.to_string()!r})"


@dataclass
class FieldComparison(FilterExpression):
    """A comparison operation on a field."""

    field_name: str
    operator: str
    value: Any

    def to_string(self) -> str:
        formatted_value = _format_value(self.value)
        return f"{self.field_name} {self.operator} {formatted_value}"


@dataclass
class RawFilter(FilterExpression):
    """A raw filter string (escape hatch for power users)."""

    expression: str

    def to_string(self) -> str:
        return self.expression


@dataclass
class AndExpression(FilterExpression):
    """`&` combination of two expressions."""

    left: FilterExpression
    right: FilterExpression

    def to_string(self) -> str:
        left_str = self.left.to_string()
        right_str = self.right.to_string()
        # Wrap in parentheses for correct precedence
        return f"({left_str}) & ({right_str})"


@dataclass
class OrExpression(FilterExpression):
    """`|` combination of two expressions."""

    left: FilterExpression
    right: FilterExpression

    def to_string(self) -> str:
        left_str = self.left.to_string()
        right_str = self.right.to_string()
        return f"({left_str}) | ({right_str})"


@dataclass
class NotExpression(FilterExpression):
    """`!` negation of an expression."""

    expr: FilterExpression

    def to_string(self) -> str:
        return f"!({self.expr.to_string()})"


class FieldBuilder:
    """Builder for field-based filter expressions."""

    def __init__(self, field_name: str):
        self._field_name = field_name

    def equals(self, value: Any) -> FieldComparison:
        """Field equals value (exact match)."""
        return FieldComparison(self._field_name, "=", value)

    def not_equals(self, value: Any) -> FieldComparison:
        """Field does not equal value."""
        return FieldComparison(self._field_name, "!=", value)

    def contains(self, value: str) -> FieldComparison:
        """Field contains substring (case-insensitive)."""
        return FieldComparison(self._field_name, "=~", value)

    def starts_with(self, value: str) -> FieldComparison:
        """Field starts with prefix."""
        return FieldComparison(self._field_name, "=^", value)

    def ends_with(self, value: str) -> FieldComparison:
        """Field ends with suffix."""
        return FieldComparison(self._field_name, "=$", value)

    def greater_than(self, value: int | float | datetime | date) -> FieldComparison:
        """Field is greater than value."""
        return FieldComparison(self._field_name, ">", value)

    def greater_than_or_equal(self, value: int | float | datetime | date) -> FieldComparison:
        """Field is greater than or equal to value."""
        return FieldComparison(self._field_name, ">=", value)

    def less_than(self, value: int | float | datetime | date) -> FieldComparison:
        """Field is less than value."""
        return FieldComparison(self._field_name, "<", value)

    def less_than_or_equal(self, value: int | float | datetime | date) -> FieldComparison:
        """Field is less than or equal to value."""
        return FieldComparison(self._field_name, "<=", value)

    def is_null(self) -> FieldComparison:
        """Field is null."""
        return FieldComparison(self._field_name, "!=", RawToken("*"))

    def is_not_null(self) -> FieldComparison:
        """Field is not null."""
        return FieldComparison(self._field_name, "=", RawToken("*"))

    def in_list(self, values: list[Any]) -> FilterExpression:
        """Field value is in the given list (OR of equals)."""
        if not values:
            raise ValueError("in_list() requires at least one value")
        expressions: list[FilterExpression] = [self.equals(v) for v in values]
        result: FilterExpression = expressions[0]
        for expr in expressions[1:]:
            result = result | expr
        return result


class Filter:
    """
    Factory for building filter expressions.

    Example:
        # Simple comparison
        Filter.field("name").contains("Acme")

        # Complex boolean logic
        (Filter.field("status").equals("Active") &
         Filter.field("type").in_list(["customer", "prospect"]))

        # Negation
        ~Filter.field("archived").equals(True)
    """

    @staticmethod
    def field(name: str) -> FieldBuilder:
        """Start building a filter on a field."""
        return FieldBuilder(name)

    @staticmethod
    def raw(expression: str) -> RawFilter:
        """
        Create a raw filter expression (escape hatch).

        Use this when you need filter syntax not supported by the builder.
        The expression is passed directly to the API without modification.

        Args:
            expression: Raw filter string (e.g., 'name =~ "Acme"')
        """
        return RawFilter(expression)

    @staticmethod
    def and_(*expressions: FilterExpression) -> FilterExpression:
        """Combine multiple expressions with `&`."""
        if not expressions:
            raise ValueError("and_() requires at least one expression")
        result = expressions[0]
        for expr in expressions[1:]:
            result = result & expr
        return result

    @staticmethod
    def or_(*expressions: FilterExpression) -> FilterExpression:
        """Combine multiple expressions with `|`."""
        if not expressions:
            raise ValueError("or_() requires at least one expression")
        result = expressions[0]
        for expr in expressions[1:]:
            result = result | expr
        return result


# Shorthand alias for convenience
F = Filter
