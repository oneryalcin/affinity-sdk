"""Tests for ISODatetime UTC normalization and parse_iso_datetime local time handling."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from click.testing import CliRunner
from httpx import Response
from pydantic import BaseModel

from affinity.cli.commands._v1_parsing import parse_iso_datetime
from affinity.cli.csv_utils import localize_iso_string, localize_row_datetimes
from affinity.cli.errors import CLIError
from affinity.models.types import ISODatetime


@pytest.mark.req("TR-012a")
class TestISODatetime:
    """Tests for ISODatetime UTC normalization."""

    def test_naive_datetime_becomes_utc(self) -> None:
        """Naive datetime is assumed UTC."""

        class Model(BaseModel):
            ts: ISODatetime

        m = Model(ts=datetime(2024, 1, 1, 12, 0, 0))
        assert m.ts.tzinfo == timezone.utc
        assert m.ts == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_utc_datetime_unchanged(self) -> None:
        """UTC datetime passes through unchanged."""

        class Model(BaseModel):
            ts: ISODatetime

        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        m = Model(ts=dt)
        assert m.ts == dt

    def test_non_utc_converted(self) -> None:
        """Non-UTC aware datetime is converted to UTC."""

        class Model(BaseModel):
            ts: ISODatetime

        # EST is UTC-5
        est = timezone(timedelta(hours=-5))
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=est)
        m = Model(ts=dt)

        # Should be converted to UTC (12:00 EST = 17:00 UTC)
        assert m.ts.tzinfo == timezone.utc
        assert m.ts.hour == 17

    def test_iso_string_with_z(self) -> None:
        """ISO string with Z suffix parsed correctly."""

        class Model(BaseModel):
            ts: ISODatetime

        m = Model(ts="2024-01-01T12:00:00Z")
        assert m.ts.tzinfo == timezone.utc
        assert m.ts == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_iso_string_naive(self) -> None:
        """Naive ISO string assumed UTC."""

        class Model(BaseModel):
            ts: ISODatetime

        m = Model(ts="2024-01-01T12:00:00")
        assert m.ts.tzinfo == timezone.utc

    def test_date_only_string(self) -> None:
        """Date-only string becomes midnight UTC."""

        class Model(BaseModel):
            ts: ISODatetime

        m = Model(ts="2024-01-01")
        assert m.ts.tzinfo == timezone.utc
        assert m.ts == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_iso_string_with_offset(self) -> None:
        """ISO string with explicit offset converted to UTC."""

        class Model(BaseModel):
            ts: ISODatetime

        m = Model(ts="2024-01-01T12:00:00-05:00")
        assert m.ts.tzinfo == timezone.utc
        assert m.ts.hour == 17  # 12:00 EST = 17:00 UTC


@pytest.mark.req("TR-012b")
class TestParseIsoDatetime:
    """Tests for parse_iso_datetime with local time handling."""

    def test_z_suffix_is_utc(self) -> None:
        """Z suffix parsed as UTC (not affected by local timezone)."""
        dt = parse_iso_datetime("2024-01-01T12:00:00Z", label="test")
        assert dt.tzinfo == timezone.utc
        assert dt == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_explicit_offset_converted_to_utc(self) -> None:
        """Explicit offset is respected and converted to UTC."""
        dt = parse_iso_datetime("2024-01-01T12:00:00-05:00", label="test")
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 17  # 12:00 EST = 17:00 UTC

    def test_naive_is_utc_aware(self) -> None:
        """Naive datetime string produces UTC-aware result."""
        dt = parse_iso_datetime("2024-01-01T12:00:00", label="test")
        assert dt.tzinfo == timezone.utc
        # Actual hour depends on system timezone - see TZ-specific tests below

    def test_date_only_is_utc_aware(self) -> None:
        """Date-only string produces UTC-aware midnight."""
        dt = parse_iso_datetime("2024-01-01", label="test")
        assert dt.tzinfo == timezone.utc
        # Hour depends on local timezone

    def test_invalid_raises_cli_error(self) -> None:
        """Invalid format raises CLIError."""
        with pytest.raises(CLIError) as exc_info:
            parse_iso_datetime("not-a-date", label="test")

        assert "Invalid test datetime" in str(exc_info.value)

    def test_explicit_utc_matches_z_suffix(self) -> None:
        """Explicit +00:00 offset equivalent to Z suffix."""
        dt1 = parse_iso_datetime("2024-01-01T12:00:00Z", label="test")
        dt2 = parse_iso_datetime("2024-01-01T12:00:00+00:00", label="test")
        assert dt1 == dt2

    @pytest.mark.skipif(
        os.environ.get("TZ") != "America/New_York",
        reason="Requires TZ=America/New_York",
    )
    def test_naive_local_est(self) -> None:
        """Naive datetime interpreted as EST when TZ=America/New_York."""
        dt = parse_iso_datetime("2024-01-01T12:00:00", label="test")
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 17  # 12:00 EST = 17:00 UTC

    @pytest.mark.skipif(
        os.environ.get("TZ") != "UTC",
        reason="Requires TZ=UTC",
    )
    def test_naive_local_utc(self) -> None:
        """Naive datetime interpreted as UTC when TZ=UTC."""
        dt = parse_iso_datetime("2024-01-01T12:00:00", label="test")
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 12  # 12:00 UTC = 12:00 UTC


@pytest.mark.req("TR-012b")
class TestCliDatetimeIntegration:
    """Integration tests for CLI datetime flag handling.

    These tests verify that --after/--before flags correctly convert
    local time to UTC before sending to the API.
    """

    @pytest.fixture
    def respx_mock(self):
        """Set up respx mock for API requests."""
        respx = pytest.importorskip("respx")
        with respx.mock(assert_all_called=False) as mock:
            yield mock

    def test_explicit_utc_sent_unchanged(self, respx_mock) -> None:
        """Explicit UTC (Z suffix) is sent to API unchanged."""
        pytest.importorskip("rich_click")
        pytest.importorskip("rich")
        pytest.importorskip("platformdirs")

        from affinity.cli.main import cli

        # Track the request URL
        captured_url = None

        def capture_request(request):
            nonlocal captured_url
            captured_url = str(request.url)
            return Response(
                200,
                json={
                    "interactions": [],
                    "next_page_token": None,
                },
            )

        respx_mock.get("https://api.affinity.co/interactions").mock(side_effect=capture_request)

        runner = CliRunner()
        # Use --before within 365 days to avoid multi-chunk requests
        result = runner.invoke(
            cli,
            [
                "--json",
                "interaction",
                "ls",
                "--type",
                "meeting",
                "--person-id",
                "123",
                "--after",
                "2024-06-01T00:00:00Z",
                "--before",
                "2024-12-01T00:00:00Z",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured_url is not None, "API was not called"

        # Parse the query parameters
        parsed = urlparse(captured_url)
        params = parse_qs(parsed.query)

        # Verify the start_time parameter is exactly what we sent (UTC)
        assert "start_time" in params
        start_time = params["start_time"][0]
        # API receives ISO string, parse it
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        assert dt.year == 2024
        assert dt.month == 6
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.minute == 0
        assert dt.tzinfo is not None  # Should be timezone-aware

    def test_explicit_offset_converted_to_utc(self, respx_mock) -> None:
        """Explicit offset (e.g., -05:00) is converted to UTC for API."""
        pytest.importorskip("rich_click")
        pytest.importorskip("rich")
        pytest.importorskip("platformdirs")

        from affinity.cli.main import cli

        captured_url = None

        def capture_request(request):
            nonlocal captured_url
            captured_url = str(request.url)
            return Response(
                200,
                json={
                    "interactions": [],
                    "next_page_token": None,
                },
            )

        respx_mock.get("https://api.affinity.co/interactions").mock(side_effect=capture_request)

        runner = CliRunner()
        # 12:00 EST (UTC-5) = 17:00 UTC
        # Use --before within 365 days to avoid multi-chunk requests
        result = runner.invoke(
            cli,
            [
                "--json",
                "interaction",
                "ls",
                "--type",
                "meeting",
                "--person-id",
                "123",
                "--after",
                "2024-06-01T12:00:00-05:00",
                "--before",
                "2024-12-01T12:00:00-05:00",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured_url is not None, "API was not called"

        parsed = urlparse(captured_url)
        params = parse_qs(parsed.query)

        assert "start_time" in params
        start_time = params["start_time"][0]
        # API receives ISO string, parse it
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        # 12:00 EST = 17:00 UTC
        assert dt.hour == 17
        assert dt.tzinfo is not None

    @pytest.mark.skipif(
        os.environ.get("TZ") != "UTC",
        reason="Requires TZ=UTC for predictable local time behavior",
    )
    def test_naive_datetime_uses_local_timezone(self, respx_mock) -> None:
        """Naive datetime (no timezone) is interpreted as local time.

        When TZ=UTC, local time equals UTC, so naive input should match UTC output.
        """
        pytest.importorskip("rich_click")
        pytest.importorskip("rich")
        pytest.importorskip("platformdirs")

        from affinity.cli.main import cli

        captured_url = None

        def capture_request(request):
            nonlocal captured_url
            captured_url = str(request.url)
            return Response(
                200,
                json={
                    "interactions": [],
                    "next_page_token": None,
                },
            )

        respx_mock.get("https://api.affinity.co/interactions").mock(side_effect=capture_request)

        runner = CliRunner()
        # Use --before within 365 days to avoid multi-chunk requests
        result = runner.invoke(
            cli,
            [
                "--json",
                "interaction",
                "ls",
                "--type",
                "meeting",
                "--person-id",
                "123",
                "--after",
                "2024-06-01T12:00:00",  # Naive - interpreted as local time
                "--before",
                "2024-12-01T12:00:00",  # Naive - interpreted as local time
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert captured_url is not None, "API was not called"

        parsed = urlparse(captured_url)
        params = parse_qs(parsed.query)

        assert "start_time" in params
        start_time = params["start_time"][0]
        # API receives ISO string, parse it
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        # When TZ=UTC, 12:00 local = 12:00 UTC
        assert dt.hour == 12
        assert dt.tzinfo is not None


@pytest.mark.req("TR-012c")
class TestCsvLocalization:
    """Tests for CSV datetime localization helpers."""

    def test_localize_utc_string(self) -> None:
        """UTC string is converted to local time."""
        result = localize_iso_string("2024-01-01T12:00:00+00:00")
        # Result should be a valid ISO string with local timezone
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None
        # Original UTC time should be preserved
        assert dt.astimezone(timezone.utc).hour == 12

    def test_localize_z_suffix(self) -> None:
        """Z suffix string is converted to local time."""
        result = localize_iso_string("2024-01-01T12:00:00Z")
        dt = datetime.fromisoformat(result)
        assert dt.tzinfo is not None
        assert dt.astimezone(timezone.utc).hour == 12

    def test_localize_invalid_returns_unchanged(self) -> None:
        """Invalid datetime string returns unchanged."""
        assert localize_iso_string("not-a-date") == "not-a-date"
        assert localize_iso_string("") == ""
        assert localize_iso_string("12345") == "12345"

    def test_localize_row_datetimes_basic(self) -> None:
        """localize_row_datetimes converts specified fields."""
        row = {
            "id": 123,
            "createdAt": "2024-01-01T12:00:00+00:00",
            "name": "Test",
        }
        result = localize_row_datetimes(row, {"createdAt"})

        # Original row unchanged
        assert row["createdAt"] == "2024-01-01T12:00:00+00:00"

        # Result has localized datetime
        assert result["id"] == 123
        assert result["name"] == "Test"
        # Verify it's valid ISO with timezone info
        dt = datetime.fromisoformat(result["createdAt"])
        assert dt.tzinfo is not None
        # Verify the instant in time is preserved (12:00 UTC)
        assert dt.astimezone(timezone.utc).hour == 12

    def test_localize_row_datetimes_missing_field(self) -> None:
        """Missing datetime fields are ignored."""
        row = {"id": 123, "name": "Test"}
        result = localize_row_datetimes(row, {"createdAt", "updatedAt"})
        assert result == row

    def test_localize_row_datetimes_non_string_field(self) -> None:
        """Non-string datetime fields are ignored."""
        row = {"id": 123, "createdAt": None}
        result = localize_row_datetimes(row, {"createdAt"})
        assert result["createdAt"] is None

    def test_localize_row_datetimes_multiple_fields(self) -> None:
        """Multiple datetime fields can be localized."""
        row = {
            "id": 123,
            "createdAt": "2024-01-01T12:00:00Z",
            "updatedAt": "2024-06-15T18:30:00Z",
        }
        result = localize_row_datetimes(row, {"createdAt", "updatedAt"})

        # Both fields should be localized
        for field in ["createdAt", "updatedAt"]:
            dt = datetime.fromisoformat(result[field])
            assert dt.tzinfo is not None
