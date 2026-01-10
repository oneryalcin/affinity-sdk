"""Tests for interaction date chunking CLI command."""

from __future__ import annotations

import pytest

from affinity.cli.commands.interaction_cmds import _resolve_date_range
from affinity.cli.errors import CLIError


@pytest.mark.req("CLI-INTERACTION-DATE-CHUNKING")
class TestResolveDateRange:
    """Tests for _resolve_date_range function."""

    def test_days_flag_sets_range(self) -> None:
        """--days flag sets correct date range from now."""
        start, end = _resolve_date_range(after=None, before=None, days=30)
        # End should be approximately now
        # Start should be 30 days before end
        delta = end - start
        assert delta.days == 30

    def test_after_flag_sets_start(self) -> None:
        """--after flag sets start date, end defaults to now."""
        # Use explicit UTC to avoid local timezone interpretation
        start, _end = _resolve_date_range(after="2024-01-01T00:00:00Z", before=None, days=None)
        assert start.year == 2024
        assert start.month == 1
        assert start.day == 1

    def test_after_and_before_explicit_range(self) -> None:
        """--after and --before set explicit range."""
        # Use explicit UTC to avoid local timezone interpretation
        start, end = _resolve_date_range(
            after="2024-01-01T00:00:00Z", before="2024-06-01T00:00:00Z", days=None
        )
        assert start.year == 2024
        assert start.month == 1
        assert start.day == 1
        assert end.year == 2024
        assert end.month == 6
        assert end.day == 1

    def test_days_and_after_mutually_exclusive(self) -> None:
        """--days and --after cannot be used together."""
        with pytest.raises(CLIError) as exc_info:
            _resolve_date_range(after="2024-01-01T00:00:00Z", before=None, days=30)
        assert "mutually exclusive" in str(exc_info.value)

    def test_no_date_flags_raises_error(self) -> None:
        """Must specify --days or --after."""
        with pytest.raises(CLIError) as exc_info:
            _resolve_date_range(after=None, before=None, days=None)
        assert "--days or --after" in str(exc_info.value)

    def test_before_only_raises_error(self) -> None:
        """--before without --after or --days raises error."""
        with pytest.raises(CLIError) as exc_info:
            _resolve_date_range(after=None, before="2024-06-01T00:00:00Z", days=None)
        assert "--days or --after" in str(exc_info.value)

    def test_start_after_end_raises_error(self) -> None:
        """Start date after end date raises error."""
        with pytest.raises(CLIError) as exc_info:
            _resolve_date_range(
                after="2024-06-01T00:00:00Z", before="2024-01-01T00:00:00Z", days=None
            )
        assert "must be before" in str(exc_info.value)

    def test_explicit_utc_in_after(self) -> None:
        """Explicit UTC (Z suffix) in --after is respected."""
        start, _end = _resolve_date_range(after="2024-01-01T12:00:00Z", before=None, days=None)
        assert start.hour == 12
        assert start.tzinfo is not None

    def test_explicit_offset_in_after(self) -> None:
        """Explicit offset in --after is converted to UTC."""
        start, _end = _resolve_date_range(after="2024-01-01T12:00:00-05:00", before=None, days=None)
        # 12:00 EST = 17:00 UTC
        assert start.hour == 17
        assert start.tzinfo is not None


# Integration tests require CLI dependencies
pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

import json  # noqa: E402
from urllib.parse import parse_qs, urlparse  # noqa: E402

from click.testing import CliRunner  # noqa: E402
from httpx import Response  # noqa: E402

from affinity.cli.main import cli  # noqa: E402


@pytest.mark.req("CLI-INTERACTION-DATE-CHUNKING")
class TestInteractionLsIntegration:
    """Integration tests for interaction ls with date chunking."""

    @pytest.fixture
    def respx_mock(self):
        """Set up respx mock for API requests."""
        respx = pytest.importorskip("respx")
        with respx.mock(assert_all_called=False) as mock:
            yield mock

    def test_multiple_chunks_makes_multiple_api_calls(self, respx_mock) -> None:
        """Date range > 365 days triggers multiple API calls."""
        call_count = 0
        captured_dates: list[tuple[str, str]] = []

        def capture_request(request):
            nonlocal call_count
            call_count += 1
            # Extract start_time and end_time from query
            parsed = urlparse(str(request.url))
            params = parse_qs(parsed.query)
            start = params.get("start_time", [""])[0]
            end = params.get("end_time", [""])[0]
            captured_dates.append((start, end))
            return Response(
                200,
                json={"interactions": [], "next_page_token": None},
            )

        respx_mock.get("https://api.affinity.co/interactions").mock(side_effect=capture_request)

        runner = CliRunner()
        # 2 years = ~2 chunks (730 days / 365 = 2)
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
                "2022-01-01T00:00:00Z",
                "--before",
                "2024-01-01T00:00:00Z",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should have made 2 API calls (730 days / 365 = 2 chunks)
        assert call_count == 2, f"Expected 2 API calls, got {call_count}"
        # Verify chunks are sequential
        assert len(captured_dates) == 2
        # First chunk starts at 2022-01-01
        assert "2022-01-01" in captured_dates[0][0]
        # Second chunk starts at 2023-01-01 (365 days later)
        assert "2023-01-01" in captured_dates[1][0]
        # Second chunk ends at 2024-01-01
        assert "2024-01-01" in captured_dates[1][1]

    def test_max_results_stops_fetching(self, respx_mock) -> None:
        """--max-results stops fetching even across chunks."""
        call_count = 0

        def mock_response(_request):
            nonlocal call_count
            call_count += 1
            # Return 10 interactions per call
            interactions = [
                {
                    "id": i + (call_count - 1) * 10,
                    "type": 0,
                    "date": "2022-06-01T00:00:00Z",
                    "subject": f"Interaction {i}",
                    "persons": [{"id": 123, "type": "external"}],
                }
                for i in range(10)
            ]
            return Response(
                200,
                json={"interactions": interactions, "next_page_token": None},
            )

        respx_mock.get("https://api.affinity.co/interactions").mock(side_effect=mock_response)

        runner = CliRunner()
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
                "2022-01-01T00:00:00Z",
                "--before",
                "2024-01-01T00:00:00Z",
                "--max-results",
                "5",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output.strip())
        # Should have exactly 5 results
        assert len(payload["data"]["interactions"]) == 5
        # Should only have made 1 API call (stopped after hitting limit)
        assert call_count == 1

    def test_csv_output_works(self, respx_mock) -> None:
        """--csv flag outputs CSV format."""
        respx_mock.get("https://api.affinity.co/interactions").mock(
            return_value=Response(
                200,
                json={
                    "interactions": [
                        {
                            "id": 100,
                            "type": 0,
                            "date": "2024-06-15T10:00:00Z",
                            "subject": "Test meeting",
                            "persons": [{"id": 123, "type": "external"}],
                        }
                    ],
                    "next_page_token": None,
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "interaction",
                "ls",
                "--type",
                "meeting",
                "--person-id",
                "123",
                "--days",
                "30",
                "--csv",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        # CSV output exits with 0
        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should have CSV header and data row
        lines = result.output.strip().split("\n")
        assert len(lines) >= 2  # Header + at least 1 row
        # Header should contain expected columns
        assert "id" in lines[0]
        assert "type" in lines[0]
        # Data should contain our test interaction
        assert "100" in lines[1]

    def test_single_chunk_metadata(self, respx_mock) -> None:
        """Single chunk (< 365 days) shows chunksProcessed=1 in metadata."""
        respx_mock.get("https://api.affinity.co/interactions").mock(
            return_value=Response(
                200,
                json={"interactions": [], "next_page_token": None},
            )
        )

        runner = CliRunner()
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
                "--days",
                "30",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output.strip())
        assert payload["data"]["metadata"]["chunksProcessed"] == 1

    def test_multiple_chunks_metadata(self, respx_mock) -> None:
        """Multiple chunks shows correct chunksProcessed in metadata."""
        respx_mock.get("https://api.affinity.co/interactions").mock(
            return_value=Response(
                200,
                json={"interactions": [], "next_page_token": None},
            )
        )

        runner = CliRunner()
        # 2 years = 2 chunks
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
                "2022-01-01T00:00:00Z",
                "--before",
                "2024-01-01T00:00:00Z",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output.strip())
        assert payload["data"]["metadata"]["chunksProcessed"] == 2

    def test_date_range_in_metadata(self, respx_mock) -> None:
        """Date range appears in metadata."""
        respx_mock.get("https://api.affinity.co/interactions").mock(
            return_value=Response(
                200,
                json={"interactions": [], "next_page_token": None},
            )
        )

        runner = CliRunner()
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
                "2024-01-01T00:00:00Z",
                "--before",
                "2024-06-01T00:00:00Z",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.output.strip())
        metadata = payload["data"]["metadata"]
        assert "dateRange" in metadata
        assert "2024-01-01" in metadata["dateRange"]["start"]
        assert "2024-06-01" in metadata["dateRange"]["end"]

    def test_csv_and_json_mutually_exclusive(self) -> None:
        """--csv and --json flags are mutually exclusive."""
        runner = CliRunner()
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
                "--days",
                "30",
                "--csv",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 2
        assert "mutually exclusive" in result.output.lower()

    def test_no_date_flags_error(self) -> None:
        """Omitting date flags raises error."""
        runner = CliRunner()
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
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 2
        assert "--days or --after" in result.output
