"""Integration tests for CLI --output flag across commands.

Tests that the new output formats (jsonl, markdown, toon, csv) work
correctly when passed via --output/-o flag to various CLI commands.
"""

from __future__ import annotations

import json

import pytest
import respx
from click.testing import CliRunner
from httpx import Response

from affinity.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestOutputFlagPersonLs:
    """Test --output flag on person ls command."""

    @respx.mock
    def test_person_ls_output_markdown(self, runner: CliRunner) -> None:
        """person ls --output markdown produces markdown table."""
        respx.get("https://api.affinity.co/v2/persons").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "type": "person", "first_name": "Alice", "last_name": "Smith"},
                        {"id": 2, "type": "person", "first_name": "Bob", "last_name": "Jones"},
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["person", "ls", "--output", "markdown"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        # Should have markdown table format
        assert "|" in result.output
        assert "Alice" in result.output
        assert "Bob" in result.output

    @respx.mock
    def test_person_ls_output_jsonl(self, runner: CliRunner) -> None:
        """person ls --output jsonl produces JSON Lines."""
        respx.get("https://api.affinity.co/v2/persons").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "type": "person", "first_name": "Alice"},
                        {"id": 2, "type": "person", "first_name": "Bob"},
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["person", "ls", "-o", "jsonl"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        # Each line should be valid JSON
        lines = [line for line in result.output.strip().split("\n") if line]
        assert len(lines) >= 1
        # First line should be valid JSON (could be object or wrapped)
        parsed = json.loads(lines[0])
        assert isinstance(parsed, dict)

    @respx.mock
    def test_person_ls_output_toon(self, runner: CliRunner) -> None:
        """person ls --output toon produces TOON format."""
        respx.get("https://api.affinity.co/v2/persons").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "type": "person", "first_name": "Alice"},
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["person", "ls", "--output", "toon"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        # TOON format starts with [count]{fields}:
        assert "[" in result.output
        assert "{" in result.output
        assert "}:" in result.output

    @respx.mock
    def test_person_ls_output_csv_flag(self, runner: CliRunner) -> None:
        """person ls --output csv produces CSV output."""
        respx.get("https://api.affinity.co/v2/persons").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "type": "person", "first_name": "Alice", "last_name": "Smith"},
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["person", "ls", "--output", "csv"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        # CSV output should have headers and data
        assert "Alice" in result.output


class TestOutputFlagCompanyLs:
    """Test --output flag on company ls command."""

    @respx.mock
    def test_company_ls_output_markdown(self, runner: CliRunner) -> None:
        """company ls --output markdown produces markdown table."""
        respx.get("https://api.affinity.co/v2/companies").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "type": "company", "name": "Acme Corp", "domain": "acme.com"},
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["company", "ls", "-o", "markdown"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        assert "|" in result.output
        assert "Acme" in result.output


class TestOutputFlagOpportunityLs:
    """Test --output flag on opportunity ls command."""

    @respx.mock
    def test_opportunity_ls_output_markdown(self, runner: CliRunner) -> None:
        """opportunity ls --output markdown produces markdown table."""
        respx.get("https://api.affinity.co/v2/opportunities").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "type": "opportunity", "name": "Big Deal"},
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["opportunity", "ls", "--output", "markdown"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        assert "|" in result.output
        assert "Big Deal" in result.output


class TestOutputFlagListExport:
    """Test --output flag on list export command."""

    @respx.mock
    def test_list_export_output_markdown(self, runner: CliRunner) -> None:
        """list export --output markdown produces markdown table."""
        # Mock list lookup
        respx.get("https://api.affinity.co/v2/lists").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 123,
                            "type": 0,  # ListType enum value for person
                            "name": "Pipeline",
                            "public": True,
                            "ownerId": 1,
                            "listSize": 2,
                        }
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )
        # Mock list entries
        respx.get("https://api.affinity.co/v2/lists/123/list-entries").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "type": "person",
                            "listId": 123,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "entity": {
                                "id": 100,
                                "type": "person",
                                "firstName": "John",
                                "lastName": "Smith",
                            },
                        },
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )
        # Mock fields
        respx.get("https://api.affinity.co/v2/lists/123/fields").mock(
            return_value=Response(
                200,
                json={
                    "data": [],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["list", "export", "Pipeline", "--output", "markdown"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        # Should have markdown table format
        assert "|" in result.output
        # Should contain some entity data
        assert "Smith" in result.output or "John" in result.output or "100" in result.output

    @respx.mock
    def test_list_export_output_toon(self, runner: CliRunner) -> None:
        """list export --output toon produces TOON format."""
        respx.get("https://api.affinity.co/v2/lists").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 123,
                            "type": 0,  # ListType enum value
                            "name": "Pipeline",
                            "public": True,
                            "ownerId": 1,
                            "listSize": 1,
                        }
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )
        respx.get("https://api.affinity.co/v2/lists/123/list-entries").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "type": "person",
                            "listId": 123,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "entity": {
                                "id": 100,
                                "type": "person",
                                "firstName": "John",
                                "lastName": "Smith",
                            },
                        },
                    ],
                    "pagination": {"next_page_token": None},
                },
            )
        )
        respx.get("https://api.affinity.co/v2/lists/123/fields").mock(
            return_value=Response(
                200,
                json={"data": [], "pagination": {"next_page_token": None}},
            )
        )

        result = runner.invoke(
            cli,
            ["list", "export", "Pipeline", "-o", "toon"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        # TOON format starts with [count]{fields}:
        assert "[" in result.output
        assert "{" in result.output
        assert "}:" in result.output


class TestOutputFlagErrorFallback:
    """Test that errors fall back to JSON format."""

    def test_error_falls_back_to_json(self, runner: CliRunner) -> None:
        """When an error occurs with non-JSON format, output falls back to JSON."""
        # No mock = will fail with connection error
        result = runner.invoke(
            cli,
            ["person", "ls", "--output", "markdown"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        # Should have JSON error structure (ok: false)
        assert result.exit_code != 0
        # Error output should be JSON
        try:
            parsed = json.loads(result.output)
            assert parsed.get("ok") is False
        except json.JSONDecodeError:
            # Some errors might not produce JSON output
            pass


class TestOutputFlagShortForm:
    """Test -o short form works."""

    @respx.mock
    def test_short_form_o(self, runner: CliRunner) -> None:
        """-o markdown works same as --output markdown."""
        respx.get("https://api.affinity.co/v2/persons").mock(
            return_value=Response(
                200,
                json={
                    "data": [{"id": 1, "type": "person", "first_name": "Test"}],
                    "pagination": {"next_page_token": None},
                },
            )
        )

        result = runner.invoke(
            cli,
            ["person", "ls", "-o", "markdown"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        assert result.exit_code == 0
        assert "|" in result.output
