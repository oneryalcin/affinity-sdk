"""Tests for the filter parser and matches() functionality."""

from __future__ import annotations

import pytest

from affinity.filters import (
    AndExpression,
    FieldComparison,
    NotExpression,
    OrExpression,
    RawFilter,
    RawToken,
    parse,
)

# =============================================================================
# Parser tests - simple conditions
# =============================================================================


def test_parse_simple_equality() -> None:
    """Test parsing simple equality expression."""
    expr = parse("name=Alice")
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "name"
    assert expr.operator == "="
    assert expr.value == "Alice"


def test_parse_simple_inequality() -> None:
    """Test parsing simple inequality expression."""
    expr = parse("name!=Bob")
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "name"
    assert expr.operator == "!="
    assert expr.value == "Bob"


def test_parse_contains() -> None:
    """Test parsing contains operator."""
    expr = parse("name=~Corp")
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "name"
    assert expr.operator == "=~"
    assert expr.value == "Corp"


def test_parse_is_null() -> None:
    """Test parsing IS NULL (!=*) expression."""
    expr = parse("email!=*")
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "email"
    assert expr.operator == "!="
    assert isinstance(expr.value, RawToken)
    assert expr.value.token == "*"


def test_parse_is_not_null() -> None:
    """Test parsing IS NOT NULL (=*) expression."""
    expr = parse("email=*")
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "email"
    assert expr.operator == "="
    assert isinstance(expr.value, RawToken)
    assert expr.value.token == "*"


def test_parse_with_whitespace() -> None:
    """Test parsing with spaces around operators."""
    expr = parse("name = Alice")
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "name"
    assert expr.value == "Alice"


def test_parse_quoted_field_name() -> None:
    """Test parsing quoted field name with spaces."""
    expr = parse('"Primary Email Status"=Valid')
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "Primary Email Status"
    assert expr.value == "Valid"


def test_parse_quoted_value() -> None:
    """Test parsing quoted value with spaces."""
    expr = parse('status="Active User"')
    assert isinstance(expr, FieldComparison)
    assert expr.field_name == "status"
    assert expr.value == "Active User"


def test_parse_quoted_with_escapes() -> None:
    """Test parsing quoted string with escapes."""
    expr = parse('name="Alice \\"Bob\\" Smith"')
    assert isinstance(expr, FieldComparison)
    assert expr.value == 'Alice "Bob" Smith'


# =============================================================================
# Parser tests - boolean operators
# =============================================================================


def test_parse_or() -> None:
    """Test parsing OR expression."""
    expr = parse("status=Active | status=Pending")
    assert isinstance(expr, OrExpression)
    assert isinstance(expr.left, FieldComparison)
    assert isinstance(expr.right, FieldComparison)


def test_parse_and() -> None:
    """Test parsing AND expression."""
    expr = parse("status=Active & role=CEO")
    assert isinstance(expr, AndExpression)
    assert isinstance(expr.left, FieldComparison)
    assert isinstance(expr.right, FieldComparison)


def test_parse_not() -> None:
    """Test parsing NOT expression."""
    expr = parse("!(status=Inactive)")
    assert isinstance(expr, NotExpression)
    assert isinstance(expr.expr, FieldComparison)


def test_parse_grouped() -> None:
    """Test parsing grouped expression with parentheses."""
    expr = parse("(status=A | status=B) & role=CEO")
    assert isinstance(expr, AndExpression)
    assert isinstance(expr.left, OrExpression)
    assert isinstance(expr.right, FieldComparison)


def test_parse_precedence() -> None:
    """Test that AND has higher precedence than OR."""
    # a=1 | b=2 & c=3 should be parsed as a=1 | (b=2 & c=3)
    expr = parse("a=1 | b=2 & c=3")
    assert isinstance(expr, OrExpression)
    assert isinstance(expr.left, FieldComparison)
    assert isinstance(expr.right, AndExpression)


def test_parse_multiple_or() -> None:
    """Test parsing multiple OR expressions."""
    expr = parse("a=1 | b=2 | c=3")
    assert isinstance(expr, OrExpression)


def test_parse_multiple_and() -> None:
    """Test parsing multiple AND expressions."""
    expr = parse("a=1 & b=2 & c=3")
    assert isinstance(expr, AndExpression)


# =============================================================================
# matches() tests - FieldComparison
# =============================================================================


def test_matches_equality() -> None:
    """Test equality matching."""
    expr = parse("name=Alice")
    assert expr.matches({"name": "Alice"})
    assert not expr.matches({"name": "Bob"})


def test_matches_inequality() -> None:
    """Test inequality matching."""
    expr = parse("name!=Bob")
    assert expr.matches({"name": "Alice"})
    assert not expr.matches({"name": "Bob"})


def test_matches_contains() -> None:
    """Test contains matching (case-insensitive)."""
    expr = parse("name=~Corp")
    assert expr.matches({"name": "Acme Corp"})
    assert expr.matches({"name": "CORP International"})
    assert not expr.matches({"name": "Acme Inc"})


def test_matches_is_null() -> None:
    """Test IS NULL matching."""
    expr = parse("email!=*")
    assert expr.matches({"email": None})
    assert expr.matches({"email": ""})
    assert expr.matches({})  # missing key
    assert not expr.matches({"email": "test@example.com"})


def test_matches_is_not_null() -> None:
    """Test IS NOT NULL matching."""
    expr = parse("email=*")
    assert expr.matches({"email": "test@example.com"})
    assert not expr.matches({"email": None})
    assert not expr.matches({"email": ""})
    assert not expr.matches({})


def test_matches_string_coercion() -> None:
    """Test that values are coerced to strings."""
    expr = parse("count=5")
    assert expr.matches({"count": 5})  # int coerced to "5"
    assert expr.matches({"count": "5"})  # already string


def test_matches_boolean_coercion() -> None:
    """Test that booleans are coerced to strings."""
    expr = parse("active=True")
    assert expr.matches({"active": True})  # bool coerced to "True"
    assert not expr.matches({"active": False})


# =============================================================================
# matches() tests - compound expressions
# =============================================================================


def test_matches_or() -> None:
    """Test OR matching."""
    expr = parse("status=Unknown | status=Valid")
    assert expr.matches({"status": "Unknown"})
    assert expr.matches({"status": "Valid"})
    assert not expr.matches({"status": "Invalid"})


def test_matches_and() -> None:
    """Test AND matching."""
    expr = parse("status=Active & role=CEO")
    assert expr.matches({"status": "Active", "role": "CEO"})
    assert not expr.matches({"status": "Active", "role": "CTO"})
    assert not expr.matches({"status": "Inactive", "role": "CEO"})


def test_matches_not() -> None:
    """Test NOT matching."""
    expr = parse("!(status=Inactive)")
    assert expr.matches({"status": "Active"})
    assert not expr.matches({"status": "Inactive"})


def test_matches_complex() -> None:
    """Test complex expression matching."""
    expr = parse("(status=A | status=B) & role=CEO")
    assert expr.matches({"status": "A", "role": "CEO"})
    assert expr.matches({"status": "B", "role": "CEO"})
    assert not expr.matches({"status": "A", "role": "CTO"})
    assert not expr.matches({"status": "C", "role": "CEO"})


def test_matches_precedence() -> None:
    """Test precedence in matching."""
    # a=1 | b=2 & c=3 should be parsed as a=1 | (b=2 & c=3)
    expr = parse("a=1 | b=2 & c=3")
    assert expr.matches({"a": "1"})  # OR short-circuits
    assert expr.matches({"b": "2", "c": "3"})  # AND on right side
    assert not expr.matches({"b": "2", "c": "4"})  # AND fails


# =============================================================================
# matches() tests - field name normalization
# =============================================================================


def test_matches_field_name_exact() -> None:
    """Test exact field name matching."""
    expr = parse('"Primary Email Status"=Valid')
    assert expr.matches({"Primary Email Status": "Valid"})


def test_matches_field_name_lowercase_fallback() -> None:
    """Test lowercase field name fallback."""
    expr = parse("Email=test@example.com")
    assert expr.matches({"email": "test@example.com"})


def test_matches_field_name_prefix_fallback() -> None:
    """Test prefixed field name fallback."""
    expr = parse("name=Alice")
    assert expr.matches({"person.name": "Alice"})


# =============================================================================
# RawFilter tests
# =============================================================================


def test_raw_filter_matches_raises() -> None:
    """Test that RawFilter.matches() raises NotImplementedError."""
    expr = RawFilter("custom raw expression")
    with pytest.raises(NotImplementedError):
        expr.matches({"any": "data"})


# =============================================================================
# Error handling tests
# =============================================================================


def test_parse_empty_expression() -> None:
    """Test that empty expression raises ValueError."""
    with pytest.raises(ValueError, match="Empty"):
        parse("")


def test_parse_whitespace_only() -> None:
    """Test that whitespace-only expression raises ValueError."""
    with pytest.raises(ValueError, match="Empty"):
        parse("   ")


def test_parse_unbalanced_parens() -> None:
    """Test that unbalanced parentheses raises ValueError."""
    with pytest.raises(ValueError, match=r"[Uu]nbalanced"):
        parse("(a=1 | b=2")


def test_parse_missing_field_name() -> None:
    """Test that missing field name raises ValueError."""
    with pytest.raises(ValueError):
        parse("=value")


def test_parse_missing_value() -> None:
    """Test that missing value raises ValueError."""
    with pytest.raises(ValueError):
        parse("field=")


def test_parse_unterminated_quote() -> None:
    """Test that unterminated quote raises ValueError."""
    with pytest.raises(ValueError, match=r"[Uu]nterminated"):
        parse('"unclosed')


def test_parse_invalid_operator() -> None:
    """Test that invalid operator syntax raises ValueError."""
    # Test invalid multi-character operators
    with pytest.raises(ValueError):
        parse("field >> value")  # >> is not a valid operator

    with pytest.raises(ValueError):
        parse("field << value")  # << is not a valid operator

    with pytest.raises(ValueError):
        parse("field <> value")  # <> is not a valid operator


def test_parse_multi_word_field_suggests_quoting() -> None:
    """Test that unquoted multi-word field names give helpful error message."""
    with pytest.raises(ValueError, match=r'Hint.*"Team Member"'):
        parse('Team Member = "LB"')

    # Three-word field name
    with pytest.raises(ValueError, match=r'Hint.*"Primary Email Status"'):
        parse("Primary Email Status = Valid")


def test_parse_unsupported_operator_lists_valid_ones() -> None:
    """Test that unsupported operators give helpful error with valid alternatives."""
    with pytest.raises(ValueError, match=r"Unsupported operator '>'.*Supported operators"):
        parse("count > 5")

    with pytest.raises(ValueError, match=r"Unsupported operator '<'.*Supported operators"):
        parse("count < 5")

    # Note: >= is tokenized as > then =, so error is about >
    with pytest.raises(ValueError, match=r"Unsupported operator '>'.*Supported operators"):
        parse("count >= 5")


def test_parse_multi_word_value_suggests_quoting() -> None:
    """Test that unquoted multi-word values give helpful error message."""
    with pytest.raises(ValueError, match=r"Hint.*Values with spaces must be quoted"):
        parse("Status = Intro Meeting")

    with pytest.raises(ValueError, match=r"Hint.*Values with spaces must be quoted"):
        parse("Status = Intro Meeting Scheduled")


def test_parse_sql_keywords_suggest_symbols() -> None:
    """Test that SQL-like AND/OR keywords suggest correct symbols."""
    with pytest.raises(ValueError, match=r"Hint.*Use '&' for AND"):
        parse("status = A AND role = B")

    with pytest.raises(ValueError, match=r"Hint.*Use '\|' for OR"):
        parse("status = A OR status = B")


def test_parse_double_equals_suggests_single() -> None:
    """Test that == suggests using single =."""
    with pytest.raises(ValueError, match=r"Hint.*Use single '=' for equality"):
        parse("status == Active")


# =============================================================================
# Integration tests - realistic use cases
# =============================================================================


def test_realistic_email_status_filter() -> None:
    """Test realistic Primary Email Status filter from the proposal."""
    # Filter for people with "Primary Email Status" being Unknown, Valid, or not set
    expr = parse(
        '"Primary Email Status"=Unknown | "Primary Email Status"=Valid | "Primary Email Status"!=*'
    )

    # Should match
    assert expr.matches({"Primary Email Status": "Unknown"})
    assert expr.matches({"Primary Email Status": "Valid"})
    assert expr.matches({"Primary Email Status": None})
    assert expr.matches({"Primary Email Status": ""})
    assert expr.matches({})  # missing key

    # Should not match
    assert not expr.matches({"Primary Email Status": "Invalid"})
    assert not expr.matches({"Primary Email Status": "Bounced"})


def test_realistic_industry_filter() -> None:
    """Test realistic industry filter."""
    expr = parse("Industry=Tech | Industry=Finance")
    assert expr.matches({"Industry": "Tech"})
    assert expr.matches({"Industry": "Finance"})
    assert not expr.matches({"Industry": "Healthcare"})


def test_realistic_combined_filter() -> None:
    """Test realistic combined filter with AND and OR."""
    # Filter for people with email set AND status is Valid
    expr = parse("email=* & status=Valid")
    assert expr.matches({"email": "test@example.com", "status": "Valid"})
    assert not expr.matches({"email": "test@example.com", "status": "Invalid"})
    assert not expr.matches({"email": None, "status": "Valid"})
    assert not expr.matches({"status": "Valid"})  # email missing


# =============================================================================
# matches() tests - array fields (multi-select dropdown support)
# =============================================================================


class TestArrayFieldMatching:
    """Test filtering on multi-select/array fields."""

    @pytest.mark.req("SDK-FILT-007")
    def test_eq_array_field_membership(self) -> None:
        """eq operator on array field checks membership."""
        expr = FieldComparison("Team Member", "=", "LB")
        assert expr.matches({"Team Member": ["LB", "MA", "RK"]})
        assert not expr.matches({"Team Member": ["MA", "RK"]})

    @pytest.mark.req("SDK-FILT-007")
    def test_eq_array_to_list_set_equality(self) -> None:
        """eq with list value checks set equality (order-insensitive)."""
        expr = FieldComparison("Team Member", "=", ["LB", "MA"])
        assert expr.matches({"Team Member": ["LB", "MA"]})
        assert expr.matches({"Team Member": ["MA", "LB"]})  # order doesn't matter
        assert not expr.matches({"Team Member": ["LB", "RK"]})

    @pytest.mark.req("SDK-FILT-007")
    def test_neq_array_field_not_in(self) -> None:
        """neq operator on array field checks value NOT in array."""
        expr = FieldComparison("Team Member", "!=", "LB")
        assert expr.matches({"Team Member": ["MA", "RK"]})  # LB not in list
        assert not expr.matches({"Team Member": ["LB", "MA"]})  # LB is in list

    @pytest.mark.req("SDK-FILT-007")
    def test_neq_array_to_list_set_inequality(self) -> None:
        """neq with list value checks set inequality."""
        expr = FieldComparison("Team Member", "!=", ["LB", "MA"])
        assert expr.matches({"Team Member": ["LB", "RK"]})  # different sets
        assert not expr.matches({"Team Member": ["MA", "LB"]})  # same set

    @pytest.mark.req("SDK-FILT-007")
    def test_contains_array_field(self) -> None:
        """contains operator on array field checks any element."""
        expr = FieldComparison("Tags", "=~", "tech")
        assert expr.matches({"Tags": ["technology", "startup"]})
        assert expr.matches({"Tags": ["Tech Company", "Finance"]})
        assert not expr.matches({"Tags": ["finance", "healthcare"]})

    @pytest.mark.req("SDK-FILT-007")
    def test_empty_array_no_match(self) -> None:
        """Empty array should not match any value."""
        expr = FieldComparison("Team Member", "=", "LB")
        assert not expr.matches({"Team Member": []})

    @pytest.mark.req("SDK-FILT-007")
    def test_single_element_array(self) -> None:
        """Single-element array should match its element."""
        expr = FieldComparison("Team Member", "=", "LB")
        assert expr.matches({"Team Member": ["LB"]})

    @pytest.mark.req("SDK-FILT-007")
    def test_array_with_int_value(self) -> None:
        """Array field with integer values."""
        expr = FieldComparison("IDs", "=", 2)
        assert expr.matches({"IDs": [1, 2, 3]})
        assert not expr.matches({"IDs": [1, 3, 5]})

    @pytest.mark.req("SDK-FILT-007")
    def test_parsed_filter_array_membership(self) -> None:
        """Test array membership via parsed filter string."""
        # Quoted field name for multi-word field
        expr = parse('"Team Member"=LB')
        assert expr.matches({"Team Member": ["LB", "MA"]})
        assert not expr.matches({"Team Member": ["MA", "RK"]})

    @pytest.mark.req("SDK-FILT-007")
    def test_parsed_filter_array_contains(self) -> None:
        """Test array contains via parsed filter string."""
        expr = parse('"Team Member"=~LB')
        assert expr.matches({"Team Member": ["LB", "MA"]})
        assert expr.matches({"Team Member": ["XLB", "MA"]})  # contains "LB"
        assert not expr.matches({"Team Member": ["MA", "RK"]})

    @pytest.mark.req("SDK-FILT-007")
    def test_scalar_field_unchanged(self) -> None:
        """Scalar fields should work as before (no regression)."""
        expr = FieldComparison("Status", "=", "Active")
        assert expr.matches({"Status": "Active"})
        assert not expr.matches({"Status": "Inactive"})
