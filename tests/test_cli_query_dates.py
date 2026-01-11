"""Tests for query date parsing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from affinity.cli.query import (
    days_since,
    days_until,
    is_relative_date,
    parse_date_value,
    parse_relative_date,
)


class TestParseRelativeDate:
    """Tests for parse_relative_date function."""

    @pytest.fixture
    def now(self) -> datetime:
        """Fixed reference time for tests."""
        return datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.req("QUERY-DATE-001")
    def test_parse_negative_days(self, now: datetime) -> None:
        """Parse -30d (30 days ago)."""
        result = parse_relative_date("-30d", now=now)
        expected = now - timedelta(days=30)
        assert result == expected

    @pytest.mark.req("QUERY-DATE-001")
    def test_parse_positive_days(self, now: datetime) -> None:
        """Parse +7d (7 days from now)."""
        result = parse_relative_date("+7d", now=now)
        expected = now + timedelta(days=7)
        assert result == expected

    @pytest.mark.req("QUERY-DATE-001")
    def test_parse_weeks(self, now: datetime) -> None:
        """Parse -4w (4 weeks ago)."""
        result = parse_relative_date("-4w", now=now)
        expected = now - timedelta(weeks=4)
        assert result == expected

    @pytest.mark.req("QUERY-DATE-001")
    def test_parse_months(self, now: datetime) -> None:
        """Parse -3m (approximately 3 months ago)."""
        result = parse_relative_date("-3m", now=now)
        expected = now - timedelta(days=90)  # 3 * 30
        assert result == expected

    @pytest.mark.req("QUERY-DATE-001")
    def test_parse_years(self, now: datetime) -> None:
        """Parse -1y (approximately 1 year ago)."""
        result = parse_relative_date("-1y", now=now)
        expected = now - timedelta(days=365)
        assert result == expected

    @pytest.mark.req("QUERY-DATE-002")
    def test_parse_now(self, now: datetime) -> None:
        """Parse 'now' keyword."""
        result = parse_relative_date("now", now=now)
        assert result == now

    @pytest.mark.req("QUERY-DATE-002")
    def test_parse_today(self, now: datetime) -> None:
        """Parse 'today' keyword (midnight)."""
        result = parse_relative_date("today", now=now)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.date() == now.date()

    def test_parse_yesterday(self, now: datetime) -> None:
        """Parse 'yesterday' keyword."""
        result = parse_relative_date("yesterday", now=now)
        expected_date = (now - timedelta(days=1)).date()
        assert result.date() == expected_date
        assert result.hour == 0

    def test_parse_tomorrow(self, now: datetime) -> None:
        """Parse 'tomorrow' keyword."""
        result = parse_relative_date("tomorrow", now=now)
        expected_date = (now + timedelta(days=1)).date()
        assert result.date() == expected_date
        assert result.hour == 0

    def test_parse_case_insensitive(self, now: datetime) -> None:
        """Keywords are case insensitive."""
        assert parse_relative_date("TODAY", now=now) == parse_relative_date("today", now=now)
        assert parse_relative_date("Now", now=now) == parse_relative_date("now", now=now)

    def test_parse_invalid_format(self) -> None:
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_relative_date("not-a-date")

    def test_parse_without_sign(self, now: datetime) -> None:
        """Parse without explicit sign (assumes positive)."""
        result = parse_relative_date("7d", now=now)
        expected = now + timedelta(days=7)
        assert result == expected


class TestParseDateValue:
    """Tests for parse_date_value function."""

    def test_parse_relative(self) -> None:
        """Parse relative date value."""
        result = parse_date_value("-30d")
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_iso_date(self) -> None:
        """Parse ISO date string."""
        result = parse_date_value("2025-06-15")
        assert result is not None
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 15

    def test_parse_iso_datetime(self) -> None:
        """Parse ISO datetime string."""
        result = parse_date_value("2025-06-15T10:30:00")
        assert result is not None
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_non_date_string(self) -> None:
        """Non-date string returns None."""
        assert parse_date_value("hello world") is None
        assert parse_date_value("alice@test.com") is None

    def test_parse_non_string(self) -> None:
        """Non-string returns None."""
        assert parse_date_value(123) is None
        assert parse_date_value(None) is None


class TestDaysSince:
    """Tests for days_since function."""

    @pytest.mark.req("QUERY-DATE-003")
    def test_days_since_past(self) -> None:
        """Calculate days since a past date."""
        now = datetime(2025, 6, 15, tzinfo=timezone.utc)
        past = datetime(2025, 6, 10, tzinfo=timezone.utc)
        assert days_since(past, now=now) == 5

    @pytest.mark.req("QUERY-DATE-003")
    def test_days_since_future(self) -> None:
        """Days since future date is negative."""
        now = datetime(2025, 6, 15, tzinfo=timezone.utc)
        future = datetime(2025, 6, 20, tzinfo=timezone.utc)
        assert days_since(future, now=now) == -5


class TestDaysUntil:
    """Tests for days_until function."""

    @pytest.mark.req("QUERY-DATE-003")
    def test_days_until_future(self) -> None:
        """Calculate days until a future date."""
        now = datetime(2025, 6, 15, tzinfo=timezone.utc)
        future = datetime(2025, 6, 20, tzinfo=timezone.utc)
        assert days_until(future, now=now) == 5

    @pytest.mark.req("QUERY-DATE-003")
    def test_days_until_past(self) -> None:
        """Days until past date is negative."""
        now = datetime(2025, 6, 15, tzinfo=timezone.utc)
        past = datetime(2025, 6, 10, tzinfo=timezone.utc)
        assert days_until(past, now=now) == -5


class TestIsRelativeDate:
    """Tests for is_relative_date function."""

    def test_relative_patterns(self) -> None:
        """Recognize relative date patterns."""
        assert is_relative_date("-30d")
        assert is_relative_date("+7d")
        assert is_relative_date("-4w")
        assert is_relative_date("-3m")
        assert is_relative_date("-1y")

    def test_keywords(self) -> None:
        """Recognize date keywords."""
        assert is_relative_date("today")
        assert is_relative_date("now")
        assert is_relative_date("yesterday")
        assert is_relative_date("tomorrow")

    def test_non_dates(self) -> None:
        """Reject non-date strings."""
        assert not is_relative_date("hello")
        assert not is_relative_date("2025-06-15")
        assert not is_relative_date("")

    def test_non_strings(self) -> None:
        """Reject non-strings."""
        assert not is_relative_date(123)
        assert not is_relative_date(None)
