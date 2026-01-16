"""Tests for affinity.cli.commands._v1_parsing module."""

from datetime import datetime, timedelta, timezone

import pytest

from affinity.cli.commands._v1_parsing import parse_date_flexible, validate_domain
from affinity.cli.errors import CLIError


class TestParseDateFlexible:
    """Tests for parse_date_flexible function."""

    @pytest.fixture
    def fixed_now(self) -> datetime:
        """Fixed reference time for deterministic tests."""
        return datetime(2026, 1, 16, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.parametrize(
        "input_value,expected_delta_days",
        [
            ("+7d", 7),
            ("+2w", 14),
            ("+1m", 30),
            ("+1y", 365),
            ("-7d", -7),
        ],
    )
    def test_relative_dates(
        self, input_value: str, expected_delta_days: int, fixed_now: datetime
    ) -> None:
        result = parse_date_flexible(input_value, label="test", now=fixed_now)
        expected = fixed_now + timedelta(days=expected_delta_days)
        assert result == expected

    @pytest.mark.parametrize(
        "input_value,expected_delta_days",
        [
            ("tomorrow", 1),
            ("today", 0),
            ("yesterday", -1),
        ],
    )
    def test_keyword_dates(
        self, input_value: str, expected_delta_days: int, fixed_now: datetime
    ) -> None:
        result = parse_date_flexible(input_value, label="test", now=fixed_now)
        # Keywords return start of day
        expected = (fixed_now + timedelta(days=expected_delta_days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        assert result == expected

    def test_now_keyword(self, fixed_now: datetime) -> None:
        result = parse_date_flexible("now", label="test", now=fixed_now)
        assert result == fixed_now

    def test_iso_date_naive_converted_to_utc(self) -> None:
        """ISO dates without timezone are interpreted as local and converted to UTC."""
        result = parse_date_flexible("2026-01-23", label="test")
        # Result should be UTC-aware
        assert result.tzinfo == timezone.utc
        # Can't assert exact date due to timezone conversion from local
        # Just verify it parses without error and is UTC

    def test_iso_date_with_timezone(self) -> None:
        """ISO dates with explicit UTC timezone are preserved."""
        result = parse_date_flexible("2026-01-23T00:00:00Z", label="test")
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 23
        assert result.tzinfo == timezone.utc

    def test_iso_datetime_utc(self) -> None:
        result = parse_date_flexible("2026-01-23T14:00:00Z", label="test")
        assert result.hour == 14
        assert result.tzinfo == timezone.utc

    def test_invalid_raises_cli_error(self) -> None:
        with pytest.raises(CLIError) as exc_info:
            parse_date_flexible("invalid", label="due-date")
        assert "due-date" in str(exc_info.value)
        assert exc_info.value.hint is not None
        assert "ISO-8601" in exc_info.value.hint
        assert "+7d" in exc_info.value.hint  # Unified hint mentions relative

    def test_empty_string_raises_cli_error(self) -> None:
        with pytest.raises(CLIError) as exc_info:
            parse_date_flexible("", label="due-date")
        assert "Missing" in str(exc_info.value)

    def test_whitespace_only_raises_cli_error(self) -> None:
        with pytest.raises(CLIError) as exc_info:
            parse_date_flexible("   ", label="due-date")
        assert "Missing" in str(exc_info.value)

    def test_case_insensitive_keywords(self, fixed_now: datetime) -> None:
        """Keywords should work regardless of case."""
        result_lower = parse_date_flexible("today", label="test", now=fixed_now)
        result_upper = parse_date_flexible("TODAY", label="test", now=fixed_now)
        result_mixed = parse_date_flexible("ToDay", label="test", now=fixed_now)
        assert result_lower == result_upper == result_mixed

    def test_relative_with_plus_sign(self, fixed_now: datetime) -> None:
        """Explicit + sign should work."""
        result = parse_date_flexible("+7d", label="test", now=fixed_now)
        expected = fixed_now + timedelta(days=7)
        assert result == expected

    def test_relative_weeks(self, fixed_now: datetime) -> None:
        """Test weeks calculation."""
        result = parse_date_flexible("+2w", label="test", now=fixed_now)
        expected = fixed_now + timedelta(weeks=2)
        assert result == expected

    def test_relative_months_approximate(self, fixed_now: datetime) -> None:
        """Months are approximated as 30 days."""
        result = parse_date_flexible("+1m", label="test", now=fixed_now)
        expected = fixed_now + timedelta(days=30)
        assert result == expected

    def test_relative_years_approximate(self, fixed_now: datetime) -> None:
        """Years are approximated as 365 days."""
        result = parse_date_flexible("+1y", label="test", now=fixed_now)
        expected = fixed_now + timedelta(days=365)
        assert result == expected


class TestValidateDomain:
    """Tests for validate_domain function."""

    def test_none_returns_none(self) -> None:
        """None input returns None."""
        assert validate_domain(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert validate_domain("") is None

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only string returns None."""
        assert validate_domain("   ") is None

    def test_valid_domain_passes_through(self) -> None:
        """Valid domain is returned unchanged."""
        assert validate_domain("example.com") == "example.com"
        assert validate_domain("sub.example.com") == "sub.example.com"
        assert validate_domain("my-company.io") == "my-company.io"

    def test_domain_with_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        assert validate_domain("  example.com  ") == "example.com"

    def test_underscore_raises_error_with_suggestion(self) -> None:
        """Domain with underscore raises CLIError with dash suggestion."""
        with pytest.raises(CLIError) as exc_info:
            validate_domain("test_company.com")
        assert "underscore" in str(exc_info.value).lower()
        assert exc_info.value.hint is not None
        assert "test-company.com" in exc_info.value.hint

    def test_multiple_underscores_all_replaced_in_hint(self) -> None:
        """All underscores are replaced in the suggestion."""
        with pytest.raises(CLIError) as exc_info:
            validate_domain("my_test_company.com")
        assert exc_info.value.hint is not None
        assert "my-test-company.com" in exc_info.value.hint

    def test_http_url_raises_error_with_extracted_domain(self) -> None:
        """HTTP URL raises CLIError with extracted domain suggestion."""
        with pytest.raises(CLIError) as exc_info:
            validate_domain("http://example.com")
        assert "URL" in str(exc_info.value)
        assert exc_info.value.hint is not None
        assert "example.com" in exc_info.value.hint

    def test_https_url_raises_error_with_extracted_domain(self) -> None:
        """HTTPS URL raises CLIError with extracted domain suggestion."""
        with pytest.raises(CLIError) as exc_info:
            validate_domain("https://example.com/path")
        assert "URL" in str(exc_info.value)
        assert exc_info.value.hint is not None
        assert "example.com" in exc_info.value.hint

    def test_space_in_domain_raises_error(self) -> None:
        """Domain with space raises CLIError."""
        with pytest.raises(CLIError) as exc_info:
            validate_domain("example .com")
        assert "space" in str(exc_info.value).lower()

    def test_custom_label_in_error(self) -> None:
        """Custom label appears in error message."""
        with pytest.raises(CLIError) as exc_info:
            validate_domain("bad_domain.com", label="primary domain")
        assert "primary domain" in str(exc_info.value)
