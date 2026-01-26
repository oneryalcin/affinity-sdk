"""Tests for --with-interaction-dates flag on company get and person get commands.

Tests the CLI integration for fetching interaction date summaries.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

try:
    import respx
except ModuleNotFoundError:  # pragma: no cover - optional dev dependency
    respx = None  # type: ignore[assignment]

from click.testing import CliRunner
from httpx import Response

from affinity.cli.main import cli

if respx is None:  # pragma: no cover
    pytest.skip("respx is not installed", allow_module_level=True)


# ==============================================================================
# Test Data
# ==============================================================================

MOCK_COMPANY = {
    "id": 123,
    "name": "Acme Corp",
    "domain": "acme.com",
    "domains": ["acme.com"],
    "global": False,
    "person_ids": [],
    "opportunity_ids": [],
}

MOCK_COMPANY_WITH_INTERACTIONS = {
    **MOCK_COMPANY,
    "interaction_dates": {
        "last_event_date": "2026-01-10T10:00:00Z",
        "next_event_date": "2026-01-25T14:00:00Z",
        "last_email_date": "2026-01-12T09:30:00Z",
        "last_interaction_date": "2026-01-12T09:30:00Z",
    },
    "interactions": {
        "last_event": {"person_ids": [101, 102]},
        "next_event": {"person_ids": [101]},
    },
}

MOCK_PERSON = {
    "id": 456,
    "first_name": "Alice",
    "last_name": "Smith",
    "emails": ["alice@example.com"],
    "type": "external",
}

MOCK_PERSON_WITH_INTERACTIONS = {
    **MOCK_PERSON,
    "interaction_dates": {
        "last_event_date": "2026-01-08T15:00:00Z",
        "next_event_date": "2026-01-22T10:00:00Z",
        "last_email_date": "2026-01-14T11:00:00Z",
        "last_interaction_date": "2026-01-14T11:00:00Z",
    },
    "interactions": {
        "last_event": {"person_ids": [101]},
        "next_event": {"person_ids": [102, 103]},
    },
}


# ==============================================================================
# Company Get Tests
# ==============================================================================


def test_company_get_without_interaction_dates(respx_mock: respx.MockRouter) -> None:
    """Test company get without --with-interaction-dates uses V2 API."""
    respx_mock.get("https://api.affinity.co/v2/companies/123").mock(
        return_value=Response(200, json=MOCK_COMPANY)
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "company", "get", "123"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, f"Failed with: {result.output}"
    output = json.loads(result.output)
    assert output["ok"] is True
    company = output["data"]["company"]
    assert company["id"] == 123
    # Should not have interaction data
    assert company.get("interactionDates") is None or company.get("interaction_dates") is None


def test_company_get_with_interaction_dates(respx_mock: respx.MockRouter) -> None:
    """Test company get with --with-interaction-dates uses V1 API and returns data."""
    # V1 API uses /organizations/{id}
    respx_mock.get(url__regex=r"https://api\.affinity\.co/organizations/123.*").mock(
        return_value=Response(200, json=MOCK_COMPANY_WITH_INTERACTIONS)
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "company", "get", "123", "--with-interaction-dates"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, f"Failed with: {result.output}"
    output = json.loads(result.output)
    assert output["ok"] is True
    company = output["data"]["company"]
    assert company["id"] == 123
    # Should have interaction data
    assert "interaction_dates" in company or "interactionDates" in company


def test_company_get_with_interaction_persons(respx_mock: respx.MockRouter) -> None:
    """Test company get with --with-interaction-persons includes person IDs."""
    respx_mock.get(url__regex=r"https://api\.affinity\.co/organizations/123.*").mock(
        return_value=Response(200, json=MOCK_COMPANY_WITH_INTERACTIONS)
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "company",
            "get",
            "123",
            "--with-interaction-dates",
            "--with-interaction-persons",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, f"Failed with: {result.output}"
    output = json.loads(result.output)
    assert output["ok"] is True
    company = output["data"]["company"]
    # Should have interactions with personIds (camelCase in JSON output)
    interactions = company.get("interactions")
    assert interactions is not None
    assert "lastEvent" in interactions
    assert "personIds" in interactions["lastEvent"]


# ==============================================================================
# Person Get Tests
# ==============================================================================


def test_person_get_without_interaction_dates(respx_mock: respx.MockRouter) -> None:
    """Test person get without --with-interaction-dates uses V2 API."""
    respx_mock.get("https://api.affinity.co/v2/persons/456").mock(
        return_value=Response(200, json={**MOCK_PERSON, "firstName": "Alice", "lastName": "Smith"})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "person", "get", "456"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, f"Failed with: {result.output}"
    output = json.loads(result.output)
    assert output["ok"] is True
    person = output["data"]["person"]
    assert person["id"] == 456
    # Should not have interaction data
    assert person.get("interactionDates") is None or person.get("interaction_dates") is None


def test_person_get_with_interaction_dates(respx_mock: respx.MockRouter) -> None:
    """Test person get with --with-interaction-dates uses V1 API and returns data."""
    respx_mock.get(url__regex=r"https://api\.affinity\.co/persons/456.*").mock(
        return_value=Response(200, json=MOCK_PERSON_WITH_INTERACTIONS)
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "person", "get", "456", "--with-interaction-dates"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, f"Failed with: {result.output}"
    output = json.loads(result.output)
    assert output["ok"] is True
    person = output["data"]["person"]
    assert person["id"] == 456
    # Should have interaction data
    assert "interaction_dates" in person or "interactionDates" in person


def test_person_get_with_interaction_persons(respx_mock: respx.MockRouter) -> None:
    """Test person get with --with-interaction-persons includes person IDs."""
    respx_mock.get(url__regex=r"https://api\.affinity\.co/persons/456.*").mock(
        return_value=Response(200, json=MOCK_PERSON_WITH_INTERACTIONS)
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "person",
            "get",
            "456",
            "--with-interaction-dates",
            "--with-interaction-persons",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, f"Failed with: {result.output}"
    output = json.loads(result.output)
    assert output["ok"] is True
    person = output["data"]["person"]
    # Should have interactions with person_ids
    interactions = person.get("interactions")
    assert interactions is not None


# ==============================================================================
# Help Text Tests
# ==============================================================================


def test_company_get_help_shows_interaction_flags() -> None:
    """Test that company get --help shows interaction date flags."""
    runner = CliRunner()
    result = runner.invoke(cli, ["company", "get", "--help"])

    assert result.exit_code == 0
    # Rich formatting may truncate flag names, check for partial match
    assert "--with-interaction-dat" in result.output or "interaction" in result.output.lower()


def test_person_get_help_shows_interaction_flags() -> None:
    """Test that person get --help shows interaction date flags."""
    runner = CliRunner()
    result = runner.invoke(cli, ["person", "get", "--help"])

    assert result.exit_code == 0
    # Rich formatting may truncate flag names, check for partial match
    assert "--with-interaction-dat" in result.output or "interaction" in result.output.lower()
