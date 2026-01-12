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
from enum import Enum, auto
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


def _get_entity_value(entity: dict[str, Any], field_name: str) -> Any:
    """
    Get a field value from an entity dict with fallback normalization.

    Tries multiple key formats to handle field name variations:
    1. Exact field name as provided
    2. Lowercase version
    3. With entity type prefix (person., company., opportunity.)
    """
    value = entity.get(field_name)
    if value is None:
        value = entity.get(field_name.lower())
    if value is None:
        for prefix in ["person.", "company.", "opportunity."]:
            value = entity.get(f"{prefix}{field_name}")
            if value is not None:
                break
    return value


class FilterExpression(ABC):
    """Base class for filter expressions."""

    @abstractmethod
    def to_string(self) -> str:
        """Convert the expression to a filter string."""
        ...

    @abstractmethod
    def matches(self, entity: dict[str, Any]) -> bool:
        """
        Evaluate filter against an entity dict (client-side).

        Used for --expand-filter in list export where filtering happens
        after fetching data from the API.
        """
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

    def matches(self, entity: dict[str, Any]) -> bool:
        """Evaluate field comparison against an entity dict.

        For multi-select dropdown fields (arrays), the operators have special semantics:
        - `=` with scalar: checks if value is IN the array (membership)
        - `=` with list: checks set equality (order-insensitive)
        - `!=` with scalar: checks if value is NOT in the array
        - `!=` with list: checks set inequality
        - `=~` (contains): checks if any array element contains the substring
        """
        value = _get_entity_value(entity, self.field_name)

        # Handle NULL checks (Affinity convention: =* means NOT NULL, !=* means IS NULL)
        if self.operator == "=" and isinstance(self.value, RawToken) and self.value.token == "*":
            return value is not None and value != ""
        if self.operator == "!=" and isinstance(self.value, RawToken) and self.value.token == "*":
            return value is None or value == ""

        # Extract target value
        target = self.value if not isinstance(self.value, RawToken) else self.value.token

        # Handle array fields (multi-select dropdowns)
        if isinstance(value, list):
            if self.operator == "=":
                # If comparing list to list, check set equality (order-insensitive)
                if isinstance(target, list):
                    try:
                        return set(value) == set(target)
                    except TypeError:
                        # Unhashable elements - fall back to sorted comparison
                        try:
                            return sorted(value) == sorted(target)
                        except TypeError:
                            return value == target
                # Scalar comparison: check membership
                return target in value
            elif self.operator == "!=":
                if isinstance(target, list):
                    try:
                        return set(value) != set(target)
                    except TypeError:
                        try:
                            return sorted(value) != sorted(target)
                        except TypeError:
                            return value != target
                return target not in value
            elif self.operator == "=~":
                # Contains: check if any array element contains the substring
                target_lower = str(target).lower()
                return any(target_lower in str(elem).lower() for elem in value)
            else:
                raise ValueError(f"Unsupported operator for client-side matching: {self.operator}")

        # Handle scalar fields - coerce to strings for comparison
        # For dropdown fields, extract the "text" property
        if isinstance(value, dict) and "text" in value:
            entity_str = str(value["text"])
        else:
            entity_str = str(value) if value is not None else ""
        target_str = str(target)

        if self.operator == "=":
            return entity_str == target_str
        elif self.operator == "!=":
            return entity_str != target_str
        elif self.operator == "=~":
            # Contains (case-insensitive)
            return target_str.lower() in entity_str.lower()
        else:
            raise ValueError(f"Unsupported operator for client-side matching: {self.operator}")


@dataclass
class RawFilter(FilterExpression):
    """A raw filter string (escape hatch for power users)."""

    expression: str

    def to_string(self) -> str:
        return self.expression

    def matches(self, entity: dict[str, Any]) -> bool:
        """RawFilter cannot be evaluated client-side."""
        raise NotImplementedError(
            "RawFilter cannot be evaluated client-side. "
            "Use structured filter expressions for --expand-filter."
        )


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

    def matches(self, entity: dict[str, Any]) -> bool:
        """Both sides must match."""
        return self.left.matches(entity) and self.right.matches(entity)


@dataclass
class OrExpression(FilterExpression):
    """`|` combination of two expressions."""

    left: FilterExpression
    right: FilterExpression

    def to_string(self) -> str:
        left_str = self.left.to_string()
        right_str = self.right.to_string()
        return f"({left_str}) | ({right_str})"

    def matches(self, entity: dict[str, Any]) -> bool:
        """Either side must match."""
        return self.left.matches(entity) or self.right.matches(entity)


@dataclass
class NotExpression(FilterExpression):
    """`!` negation of an expression."""

    expr: FilterExpression

    def to_string(self) -> str:
        return f"!({self.expr.to_string()})"

    def matches(self, entity: dict[str, Any]) -> bool:
        """Invert the inner expression."""
        return not self.expr.matches(entity)


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


# =============================================================================
# Filter String Parser
# =============================================================================


class _TokenType(Enum):
    """Token types for the filter parser."""

    FIELD = auto()  # Field name (quoted or unquoted)
    OPERATOR = auto()  # =, !=, =~
    VALUE = auto()  # Value (quoted, unquoted, or *)
    AND = auto()  # &
    OR = auto()  # |
    NOT = auto()  # !
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    EOF = auto()  # End of input


@dataclass
class _Token:
    """A token from the filter string."""

    type: _TokenType
    value: str
    pos: int  # Position in original string for error messages


class _Tokenizer:
    """Tokenizer for filter strings."""

    # Operators that can appear after field names
    OPERATORS = ("!=", "=~", "=")

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def _skip_whitespace(self) -> None:
        """Skip whitespace characters."""
        while self.pos < self.length and self.text[self.pos] in " \t\n\r":
            self.pos += 1

    def _read_quoted_string(self) -> str:
        """Read a quoted string, handling escapes."""
        assert self.text[self.pos] == '"'
        start_pos = self.pos
        self.pos += 1  # Skip opening quote
        result: list[str] = []

        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch == '"':
                self.pos += 1  # Skip closing quote
                return "".join(result)
            elif ch == "\\":
                self.pos += 1
                if self.pos >= self.length:
                    raise ValueError(
                        f"Unexpected end of string after backslash at position {self.pos}"
                    )
                escaped = self.text[self.pos]
                if escaped == "n":
                    result.append("\n")
                elif escaped == "t":
                    result.append("\t")
                elif escaped == "r":
                    result.append("\r")
                elif escaped in ('"', "\\"):
                    result.append(escaped)
                else:
                    result.append(escaped)
                self.pos += 1
            else:
                result.append(ch)
                self.pos += 1

        raise ValueError(f"Unterminated quoted string starting at position {start_pos}")

    def _read_unquoted(self, stop_chars: str) -> str:
        """Read an unquoted token until a stop character or whitespace."""
        start = self.pos
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch in stop_chars or ch in " \t\n\r":
                break
            self.pos += 1
        return self.text[start : self.pos]

    def _peek_operator(self) -> str | None:
        """Check if current position starts with an operator."""
        for op in self.OPERATORS:
            if self.text[self.pos : self.pos + len(op)] == op:
                return op
        return None

    def tokenize(self) -> list[_Token]:
        """Tokenize the entire filter string."""
        tokens: list[_Token] = []

        while True:
            self._skip_whitespace()

            if self.pos >= self.length:
                tokens.append(_Token(_TokenType.EOF, "", self.pos))
                break

            ch = self.text[self.pos]
            start_pos = self.pos

            # Single-character tokens
            if ch == "(":
                tokens.append(_Token(_TokenType.LPAREN, "(", start_pos))
                self.pos += 1
            elif ch == ")":
                tokens.append(_Token(_TokenType.RPAREN, ")", start_pos))
                self.pos += 1
            elif ch == "&":
                tokens.append(_Token(_TokenType.AND, "&", start_pos))
                self.pos += 1
            elif ch == "|":
                tokens.append(_Token(_TokenType.OR, "|", start_pos))
                self.pos += 1
            elif ch == "!":
                # Check if it's != operator or standalone NOT
                if self.pos + 1 < self.length and self.text[self.pos + 1] == "=":
                    # This is != operator, will be handled as OPERATOR
                    op = self._peek_operator()
                    if op:
                        tokens.append(_Token(_TokenType.OPERATOR, op, start_pos))
                        self.pos += len(op)
                    else:
                        raise ValueError(f"Unexpected character at position {start_pos}")
                else:
                    tokens.append(_Token(_TokenType.NOT, "!", start_pos))
                    self.pos += 1
            elif ch == '"':
                # Quoted string - could be field name or value depending on context
                value = self._read_quoted_string()
                # Determine token type based on context (what comes next)
                self._skip_whitespace()
                if self.pos < self.length and self._peek_operator():
                    tokens.append(_Token(_TokenType.FIELD, value, start_pos))
                else:
                    tokens.append(_Token(_TokenType.VALUE, value, start_pos))
            elif ch == "*":
                # Wildcard value
                tokens.append(_Token(_TokenType.VALUE, "*", start_pos))
                self.pos += 1
            else:
                # Check for operator first
                op = self._peek_operator()
                if op:
                    tokens.append(_Token(_TokenType.OPERATOR, op, start_pos))
                    self.pos += len(op)
                else:
                    # Unquoted field name or value
                    # Read until operator, boolean, paren, or whitespace
                    value = self._read_unquoted('=!&|()"')
                    if not value:
                        raise ValueError(f"Unexpected character '{ch}' at position {start_pos}")

                    # Determine token type based on what comes next
                    self._skip_whitespace()
                    if self.pos < self.length and self._peek_operator():
                        tokens.append(_Token(_TokenType.FIELD, value, start_pos))
                    else:
                        tokens.append(_Token(_TokenType.VALUE, value, start_pos))

        return tokens


class _Parser:
    """Recursive descent parser for filter expressions."""

    def __init__(self, tokens: list[_Token]):
        self.tokens = tokens
        self.pos = 0

    def _current(self) -> _Token:
        """Get current token."""
        return self.tokens[self.pos]

    def _advance(self) -> _Token:
        """Advance to next token and return previous."""
        token = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def _expect(self, token_type: _TokenType, context: str = "") -> _Token:
        """Expect a specific token type, raise if not found."""
        token = self._current()
        if token.type != token_type:
            ctx = f" {context}" if context else ""
            raise ValueError(
                f"Expected {token_type.name}{ctx} at position {token.pos}, "
                f"got {token.type.name} '{token.value}'"
            )
        return self._advance()

    def parse(self) -> FilterExpression:
        """Parse the token stream into a FilterExpression."""
        if self._current().type == _TokenType.EOF:
            raise ValueError("Empty filter expression")

        expr = self._parse_or_expr()

        if self._current().type != _TokenType.EOF:
            token = self._current()
            # Check if this looks like a multi-word value (extra word after comparison)
            if token.type in (_TokenType.VALUE, _TokenType.FIELD):
                # Check for SQL-like boolean keywords
                upper_val = token.value.upper()
                if upper_val == "AND":
                    raise ValueError(
                        f"Unexpected 'AND' at position {token.pos}. "
                        f"Hint: Use '&' for AND: expr1 & expr2"
                    )
                if upper_val == "OR":
                    raise ValueError(
                        f"Unexpected 'OR' at position {token.pos}. "
                        f"Hint: Use '|' for OR: expr1 | expr2"
                    )
                # Look back to find the previous value to suggest quoting
                # Collect remaining words
                remaining_words = [token.value]
                pos = self.pos + 1
                while pos < len(self.tokens) - 1:
                    next_tok = self.tokens[pos]
                    if next_tok.type in (_TokenType.VALUE, _TokenType.FIELD):
                        remaining_words.append(next_tok.value)
                        pos += 1
                    else:
                        break
                if len(remaining_words) == 1:
                    raise ValueError(
                        f"Unexpected token '{token.value}' at position {token.pos}. "
                        f'Hint: Values with spaces must be quoted: "... {token.value}"'
                    )
                else:
                    combined = " ".join(remaining_words)
                    raise ValueError(
                        f"Unexpected token '{token.value}' at position {token.pos}. "
                        f'Hint: Values with spaces must be quoted: "...{combined}"'
                    )
            raise ValueError(f"Unexpected token '{token.value}' at position {token.pos}")

        return expr

    def _parse_or_expr(self) -> FilterExpression:
        """Parse OR expressions (lowest precedence)."""
        left = self._parse_and_expr()

        while self._current().type == _TokenType.OR:
            self._advance()  # consume |
            right = self._parse_and_expr()
            left = OrExpression(left, right)

        return left

    def _parse_and_expr(self) -> FilterExpression:
        """Parse AND expressions (medium precedence)."""
        left = self._parse_not_expr()

        while self._current().type == _TokenType.AND:
            self._advance()  # consume &
            right = self._parse_not_expr()
            left = AndExpression(left, right)

        return left

    def _parse_not_expr(self) -> FilterExpression:
        """Parse NOT expressions (high precedence)."""
        if self._current().type == _TokenType.NOT:
            self._advance()  # consume !
            expr = self._parse_not_expr()  # NOT is right-associative
            return NotExpression(expr)

        return self._parse_atom()

    def _parse_atom(self) -> FilterExpression:
        """Parse atomic expressions: comparisons or parenthesized expressions."""
        token = self._current()

        # Parenthesized expression
        if token.type == _TokenType.LPAREN:
            self._advance()  # consume (
            expr = self._parse_or_expr()
            closing = self._current()
            if closing.type != _TokenType.RPAREN:
                raise ValueError(f"Unbalanced parentheses: expected ')' at position {closing.pos}")
            self._advance()  # consume )
            return expr

        # Field comparison
        if token.type == _TokenType.FIELD:
            return self._parse_comparison()

        # Error cases
        if token.type == _TokenType.EOF:
            raise ValueError("Unexpected end of expression")
        if token.type == _TokenType.OPERATOR:
            raise ValueError(
                f"Missing field name before operator '{token.value}' at position {token.pos}"
            )
        if token.type == _TokenType.VALUE:
            # This could be an unquoted field name that wasn't recognized
            # Try to parse it as a comparison
            return self._parse_comparison_from_value()

        raise ValueError(f"Unexpected token '{token.value}' at position {token.pos}")

    def _parse_comparison(self) -> FilterExpression:
        """Parse a field comparison expression."""
        field_token = self._expect(_TokenType.FIELD, "for field name")
        field_name = field_token.value

        op_token = self._current()
        if op_token.type != _TokenType.OPERATOR:
            raise ValueError(
                f"Expected operator after field name at position {op_token.pos}, "
                f"got {op_token.type.name}"
            )
        self._advance()
        operator = op_token.value

        value_token = self._current()
        if value_token.type not in (_TokenType.VALUE, _TokenType.FIELD):
            # Check for == instead of =
            if value_token.type == _TokenType.OPERATOR and value_token.value == "=":
                raise ValueError(
                    f"Unexpected '=' at position {value_token.pos}. "
                    f"Hint: Use single '=' for equality, not '=='"
                )
            raise ValueError(f"Expected value after operator at position {value_token.pos}")
        self._advance()

        # Convert value to appropriate type
        if value_token.value == "*":
            value: Any = RawToken("*")
        else:
            value = value_token.value

        return FieldComparison(field_name, operator, value)

    def _parse_comparison_from_value(self) -> FilterExpression:
        """Parse a comparison where the field was tokenized as VALUE."""
        # This happens when field name isn't followed by operator immediately
        value_token = self._advance()
        field_name = value_token.value

        op_token = self._current()
        if op_token.type != _TokenType.OPERATOR:
            # Check if this looks like a multi-word field name (next token is word, not operator)
            # Note: the next word might be tokenized as FIELD if it's followed by an operator
            if op_token.type in (_TokenType.VALUE, _TokenType.FIELD):
                # Check if it looks like an unsupported operator (>, <, >=, <=, etc.)
                if op_token.value in (">", "<", ">=", "<=", "<>", ">>", "<<"):
                    raise ValueError(
                        f"Unsupported operator '{op_token.value}' at position {op_token.pos}. "
                        f"Supported operators: = (equals), != (not equals), =~ (contains)"
                    )
                # Collect subsequent words to suggest the full field name
                words = [field_name, op_token.value]
                pos = self.pos + 1
                while pos < len(self.tokens) - 1:
                    next_tok = self.tokens[pos]
                    if next_tok.type == _TokenType.OPERATOR:
                        break
                    if next_tok.type in (_TokenType.VALUE, _TokenType.FIELD):
                        # Skip operator-like tokens
                        if next_tok.value in (">", "<", ">=", "<=", "<>"):
                            break
                        words.append(next_tok.value)
                        pos += 1
                    else:
                        break
                suggested_field = " ".join(words)
                raise ValueError(
                    f"Expected operator after '{field_name}' at position {op_token.pos}. "
                    f'Hint: For multi-word field names, use quotes: "{suggested_field}"'
                )
            raise ValueError(f"Expected operator after '{field_name}' at position {op_token.pos}")
        self._advance()
        operator = op_token.value

        next_token = self._current()
        if next_token.type not in (_TokenType.VALUE, _TokenType.FIELD):
            # Check for == instead of =
            if next_token.type == _TokenType.OPERATOR and next_token.value == "=":
                raise ValueError(
                    f"Unexpected '=' at position {next_token.pos}. "
                    f"Hint: Use single '=' for equality, not '=='"
                )
            raise ValueError(f"Expected value after operator at position {next_token.pos}")
        self._advance()

        if next_token.value == "*":
            value: Any = RawToken("*")
        else:
            value = next_token.value

        return FieldComparison(field_name, operator, value)


def parse(filter_string: str) -> FilterExpression:
    """
    Parse a filter string into a FilterExpression AST.

    This function converts a human-readable filter string into a structured
    FilterExpression that can be used for client-side filtering with matches().

    Args:
        filter_string: The filter expression to parse

    Returns:
        A FilterExpression AST representing the filter

    Raises:
        ValueError: If the filter string is invalid

    Examples:
        >>> expr = parse('name = "Alice"')
        >>> expr.matches({"name": "Alice"})
        True

        >>> expr = parse('status = Active | status = Pending')
        >>> expr.matches({"status": "Active"})
        True

        >>> expr = parse('email = *')  # IS NOT NULL
        >>> expr.matches({"email": "test@example.com"})
        True

        >>> expr = parse('email != *')  # IS NULL
        >>> expr.matches({"email": None})
        True
    """
    if not filter_string or not filter_string.strip():
        raise ValueError("Empty filter expression")

    tokenizer = _Tokenizer(filter_string)
    tokens = tokenizer.tokenize()
    parser = _Parser(tokens)
    return parser.parse()
