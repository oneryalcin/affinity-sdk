"""Tests for CSV export functionality in person, company, and opportunity list commands."""

from __future__ import annotations

import csv
import json
from pathlib import Path

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
# Person CSV Export Tests
# ==============================================================================


def test_person_ls_csv_basic(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test basic CSV export for person ls command."""
    respx_mock.get("https://api.affinity.co/v2/persons").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1,
                        "firstName": "Alice",
                        "lastName": "Smith",
                        "primaryEmailAddress": "alice@example.com",
                    },
                    {
                        "id": 2,
                        "firstName": "Bob",
                        "lastName": "Jones",
                        "primaryEmailAddress": "bob@example.com",
                    },
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "people.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "person", "ls", "--all", "--csv", str(csv_file)],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert "csv" in payload["data"]
    assert payload["data"]["rowsWritten"] == 2

    # Verify CSV file was created and contains correct data
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["id"] == "1"
        assert rows[0]["name"] == "Alice Smith"
        assert rows[0]["primaryEmail"] == "alice@example.com"
        assert rows[1]["id"] == "2"
        assert rows[1]["name"] == "Bob Jones"


def test_person_ls_csv_with_bom(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test CSV export with BOM for person ls command."""
    respx_mock.get("https://api.affinity.co/v2/persons").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1,
                        "firstName": "Alice",
                        "lastName": "Smith",
                        "primaryEmailAddress": "alice@example.com",
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "people_bom.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "person", "ls", "--all", "--csv", str(csv_file), "--csv-bom"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 1

    # Verify BOM is present
    assert csv_file.exists()
    with csv_file.open("rb") as f:
        first_bytes = f.read(3)
        assert first_bytes == b"\xef\xbb\xbf"  # UTF-8 BOM


def test_person_ls_csv_empty_results(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test CSV export with empty results for person ls command."""
    respx_mock.get("https://api.affinity.co/v2/persons").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "people_empty.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "person", "ls", "--all", "--csv", str(csv_file)],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 0

    # Verify empty file was created
    assert csv_file.exists()
    assert csv_file.stat().st_size == 0


# ==============================================================================
# Company CSV Export Tests
# ==============================================================================


def test_company_ls_csv_basic(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test basic CSV export for company ls command."""
    respx_mock.get("https://api.affinity.co/v2/companies").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 100,
                        "name": "Acme Corp",
                        "domain": "acme.com",
                    },
                    {
                        "id": 101,
                        "name": "Beta Inc",
                        "domain": "beta.com",
                    },
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "companies.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "company", "ls", "--all", "--csv", str(csv_file)],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert "csv" in payload["data"]
    assert payload["data"]["rowsWritten"] == 2

    # Verify CSV file was created and contains correct data
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["id"] == "100"
        assert rows[0]["name"] == "Acme Corp"
        assert rows[0]["domain"] == "acme.com"
        assert rows[1]["id"] == "101"
        assert rows[1]["name"] == "Beta Inc"


def test_company_ls_csv_with_bom(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test CSV export with BOM for company ls command."""
    respx_mock.get("https://api.affinity.co/v2/companies").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 100,
                        "name": "Acme Corp",
                        "domain": "acme.com",
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "companies_bom.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "company", "ls", "--all", "--csv", str(csv_file), "--csv-bom"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 1

    # Verify BOM is present
    assert csv_file.exists()
    with csv_file.open("rb") as f:
        first_bytes = f.read(3)
        assert first_bytes == b"\xef\xbb\xbf"  # UTF-8 BOM


def test_company_ls_csv_empty_results(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test CSV export with empty results for company ls command."""
    respx_mock.get("https://api.affinity.co/v2/companies").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "companies_empty.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "company", "ls", "--all", "--csv", str(csv_file)],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 0

    # Verify empty file was created
    assert csv_file.exists()
    assert csv_file.stat().st_size == 0


# ==============================================================================
# Opportunity CSV Export Tests
# ==============================================================================


def test_opportunity_ls_csv_basic(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test basic CSV export for opportunity ls command."""
    respx_mock.get("https://api.affinity.co/v2/opportunities").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 10,
                        "name": "Seed Round",
                        "listId": 41780,
                    },
                    {
                        "id": 11,
                        "name": "Series A",
                        "listId": 41780,
                    },
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "opportunities.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "opportunity", "ls", "--all", "--csv", str(csv_file)],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert "csv" in payload["data"]
    assert payload["data"]["rowsWritten"] == 2

    # Verify CSV file was created and contains correct data
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["id"] == "10"
        assert rows[0]["name"] == "Seed Round"
        assert rows[0]["listId"] == "41780"
        assert rows[1]["id"] == "11"
        assert rows[1]["name"] == "Series A"


def test_opportunity_ls_csv_with_bom(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test CSV export with BOM for opportunity ls command."""
    respx_mock.get("https://api.affinity.co/v2/opportunities").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 10,
                        "name": "Seed Round",
                        "listId": 41780,
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "opportunities_bom.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "opportunity", "ls", "--all", "--csv", str(csv_file), "--csv-bom"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 1

    # Verify BOM is present
    assert csv_file.exists()
    with csv_file.open("rb") as f:
        first_bytes = f.read(3)
        assert first_bytes == b"\xef\xbb\xbf"  # UTF-8 BOM


def test_opportunity_ls_csv_empty_results(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test CSV export with empty results for opportunity ls command."""
    respx_mock.get("https://api.affinity.co/v2/opportunities").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    csv_file = tmp_path / "opportunities_empty.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "opportunity", "ls", "--all", "--csv", str(csv_file)],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 0

    # Verify empty file was created
    assert csv_file.exists()
    assert csv_file.stat().st_size == 0


# ==============================================================================
# List Export with --expand Tests
# ==============================================================================


def test_list_export_expand_invalid_on_person_list(
    respx_mock: respx.MockRouter,
) -> None:
    """Test that --expand people fails on a person list (only companies is valid)."""
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Contacts",
                "type": 0,  # person
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 10,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "list", "export", "12345", "--expand", "people", "--all"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert payload["ok"] is False
    assert "not valid for person lists" in payload["error"]["message"]
    assert payload["error"]["details"]["validExpand"] == ["companies", "opportunities"]


def test_list_export_expand_invalid_on_company_list(
    respx_mock: respx.MockRouter,
) -> None:
    """Test that --expand companies fails on a company list (only people is valid)."""
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Organizations",
                "type": 1,  # organization
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 10,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "list", "export", "12345", "--expand", "companies", "--all"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert payload["ok"] is False
    assert "not valid for organization lists" in payload["error"]["message"]
    assert payload["error"]["details"]["validExpand"] == ["opportunities", "people"]


def test_list_export_expand_cursor_combination_fails(
    respx_mock: respx.MockRouter,
) -> None:
    """Test that --cursor cannot be combined with --expand."""
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 10,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--cursor",
            "abc123",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert payload["ok"] is False
    assert "--cursor cannot be combined with --expand" in payload["error"]["message"]


def test_list_export_expand_people_csv_flat(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test list export with --expand people produces flat CSV with one row per person."""
    # Mock list metadata
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 2,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [{"id": "f1", "name": "Status", "type": "dropdown", "valueType": None}],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "opportunity",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 5001, "name": "Deal One"},
                        "fields": {"data": {"f1": "Active"}},
                    },
                    {
                        "id": 1002,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "opportunity",
                        "createdAt": "2024-01-02T00:00:00Z",
                        "entity": {"id": 5002, "name": "Deal Two"},
                        "fields": {"data": {"f1": "Closed"}},
                    },
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 opportunity get for associations (entry 1 - 2 people)
    respx_mock.get("https://api.affinity.co/opportunities/5001").mock(
        return_value=Response(
            200,
            json={
                "id": 5001,
                "name": "Deal One",
                "list_id": 12345,
                "person_ids": [101, 102],
                "organization_ids": [],
            },
        )
    )
    # Mock V1 opportunity get for associations (entry 2 - 1 person)
    respx_mock.get("https://api.affinity.co/opportunities/5002").mock(
        return_value=Response(
            200,
            json={
                "id": 5002,
                "name": "Deal Two",
                "list_id": 12345,
                "person_ids": [103],
                "organization_ids": [],
            },
        )
    )

    # Mock person details
    respx_mock.get("https://api.affinity.co/persons/101").mock(
        return_value=Response(
            200,
            json={
                "id": 101,
                "first_name": "Alice",
                "last_name": "Smith",
                "emails": ["alice@example.com"],
                "type": 1,
            },
        )
    )
    respx_mock.get("https://api.affinity.co/persons/102").mock(
        return_value=Response(
            200,
            json={
                "id": 102,
                "first_name": "Bob",
                "last_name": "Jones",
                "emails": ["bob@example.com"],
                "type": 1,
            },
        )
    )
    respx_mock.get("https://api.affinity.co/persons/103").mock(
        return_value=Response(
            200,
            json={
                "id": 103,
                "first_name": "Carol",
                "last_name": "White",
                "emails": ["carol@example.com"],
                "type": 1,
            },
        )
    )

    csv_file = tmp_path / "opps-with-people.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--all",
            "--csv",
            str(csv_file),
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 3  # 2 people for entry 1 + 1 for entry 2

    # Verify entriesProcessed and associationsFetched in JSON output (Gap fix)
    assert payload["data"]["entriesProcessed"] == 2
    assert payload["data"]["associationsFetched"]["people"] == 3

    # Verify CSV content
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 3

        # First entry, first person
        assert rows[0]["listEntryId"] == "1001"
        assert rows[0]["entityId"] == "5001"
        assert rows[0]["entityName"] == "Deal One"
        assert rows[0]["expandedType"] == "person"
        assert rows[0]["expandedId"] == "101"
        assert rows[0]["expandedName"] == "Alice Smith"
        assert rows[0]["expandedEmail"] == "alice@example.com"

        # First entry, second person
        assert rows[1]["listEntryId"] == "1001"
        assert rows[1]["expandedId"] == "102"
        assert rows[1]["expandedName"] == "Bob Jones"

        # Second entry, first person
        assert rows[2]["listEntryId"] == "1002"
        assert rows[2]["entityId"] == "5002"
        assert rows[2]["expandedId"] == "103"
        assert rows[2]["expandedName"] == "Carol White"


def test_list_export_expand_zero_associations(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test that entries with zero associations still appear in output."""
    # Mock list metadata
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock list entries with one entry that has no associations
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "opportunity",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 5001, "name": "Empty Deal"},
                        "fields": {"data": {}},
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 opportunity get for associations (no people)
    respx_mock.get("https://api.affinity.co/opportunities/5001").mock(
        return_value=Response(
            200,
            json={
                "id": 5001,
                "name": "Empty Deal",
                "list_id": 12345,
                "person_ids": [],
                "organization_ids": [],
            },
        )
    )

    csv_file = tmp_path / "opps-empty.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--all",
            "--csv",
            str(csv_file),
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 1  # Still 1 row for the entry

    # Verify CSV content has empty expansion columns
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["listEntryId"] == "1001"
        assert rows[0]["expandedType"] == ""
        assert rows[0]["expandedId"] == ""
        assert rows[0]["expandedName"] == ""
        assert rows[0]["expandedEmail"] == ""


def test_list_export_expand_json_output(respx_mock: respx.MockRouter) -> None:
    """Test list export with --expand produces JSON with nested arrays."""
    # Mock list metadata
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "opportunity",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 5001, "name": "Deal One"},
                        "fields": {"data": {}},
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 opportunity get for associations
    respx_mock.get("https://api.affinity.co/opportunities/5001").mock(
        return_value=Response(
            200,
            json={
                "id": 5001,
                "name": "Deal One",
                "list_id": 12345,
                "person_ids": [101],
                "organization_ids": [201],
            },
        )
    )

    # Mock person details
    respx_mock.get("https://api.affinity.co/persons/101").mock(
        return_value=Response(
            200,
            json={
                "id": 101,
                "first_name": "Alice",
                "last_name": "Smith",
                "emails": ["alice@example.com"],
                "type": 1,
            },
        )
    )

    # Mock company details
    respx_mock.get("https://api.affinity.co/organizations/201").mock(
        return_value=Response(
            200,
            json={
                "id": 201,
                "name": "Acme Corp",
                "domain": "acme.com",
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--expand",
            "companies",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())

    # Check nested arrays
    rows = payload["data"]["rows"]
    assert len(rows) == 1
    assert "people" in rows[0]
    assert "companies" in rows[0]
    assert len(rows[0]["people"]) == 1
    assert len(rows[0]["companies"]) == 1
    assert rows[0]["people"][0]["id"] == 101
    assert rows[0]["people"][0]["name"] == "Alice Smith"
    assert rows[0]["companies"][0]["id"] == 201
    assert rows[0]["companies"][0]["name"] == "Acme Corp"

    # Check summary data
    assert payload["data"]["entriesProcessed"] == 1
    assert payload["data"]["associationsFetched"]["people"] == 1
    assert payload["data"]["associationsFetched"]["companies"] == 1


def test_list_export_dry_run_with_expand(respx_mock: respx.MockRouter) -> None:
    """Test --dry-run output includes expand info."""
    # Mock list metadata with entry count
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 50,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--expand",
            "companies",
            "--dry-run",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())

    assert "expand" in payload["data"]
    assert sorted(payload["data"]["expand"]) == ["companies", "people"]
    assert payload["data"]["expandMaxResults"] == 100
    assert "estimatedApiCalls" in payload["data"]
    assert "get_associations" in payload["data"]["estimatedApiCalls"]["note"]

    # Verify listName and estimatedEntries are included (gap fix)
    assert payload["data"]["listName"] == "Pipeline"
    assert payload["data"]["estimatedEntries"] == 50


def test_list_export_expand_fields_requires_expand() -> None:
    """Test --expand-fields without --expand fails with clear error."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand-fields",
            "Status",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert "--expand-fields and --expand-field-type require --expand" in payload["error"]["message"]
    assert payload["error"]["type"] == "usage_error"


def test_list_export_expand_field_type_requires_expand() -> None:
    """Test --expand-field-type without --expand fails with clear error."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand-field-type",
            "global",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert "--expand-fields and --expand-field-type require --expand" in payload["error"]["message"]
    assert payload["error"]["type"] == "usage_error"


def test_list_export_expand_all_with_max_results_warning(respx_mock: respx.MockRouter) -> None:
    """Test --expand-all + --expand-max-results emits warning."""
    # Mock list metadata
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "opportunity",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 5001, "name": "Deal"},
                        "fields": {"data": {}},
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 opportunity for associations
    respx_mock.get("https://api.affinity.co/opportunities/5001").mock(
        return_value=Response(
            200,
            json={
                "id": 5001,
                "name": "Deal",
                "list_id": 12345,
                "person_ids": [],
                "organization_ids": [],
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--expand-all",
            "--expand-max-results",
            "50",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())

    # Check warning is present in either meta.warnings or top-level warnings
    warnings_list = payload.get("warnings", []) or payload.get("meta", {}).get("warnings", [])
    assert any("--expand-all" in w and "ignoring" in w for w in warnings_list)


def test_list_export_expand_csv_mode_nested(respx_mock: respx.MockRouter, tmp_path: object) -> None:
    """Test --csv-mode nested outputs JSON arrays in CSV columns."""
    csv_file = Path(tmp_path) / "nested.csv"  # type: ignore[arg-type]

    # Mock list metadata
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [{"id": "f1", "name": "Status", "type": "dropdown", "valueType": None}],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "opportunity",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 5001, "name": "Deal One"},
                        "fields": {"data": {"f1": "Active"}},
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 opportunity for associations
    respx_mock.get("https://api.affinity.co/opportunities/5001").mock(
        return_value=Response(
            200,
            json={
                "id": 5001,
                "name": "Deal One",
                "list_id": 12345,
                "person_ids": [101, 102],
                "organization_ids": [201],
            },
        )
    )

    # Mock person details
    respx_mock.get("https://api.affinity.co/persons/101").mock(
        return_value=Response(
            200,
            json={
                "id": 101,
                "first_name": "Alice",
                "last_name": "Smith",
                "emails": ["alice@example.com"],
                "type": 1,
            },
        )
    )
    respx_mock.get("https://api.affinity.co/persons/102").mock(
        return_value=Response(
            200,
            json={
                "id": 102,
                "first_name": "Bob",
                "last_name": "Jones",
                "emails": ["bob@example.com"],
                "type": 1,
            },
        )
    )

    # Mock company details
    respx_mock.get("https://api.affinity.co/organizations/201").mock(
        return_value=Response(
            200,
            json={
                "id": 201,
                "name": "Acme Corp",
                "domain": "acme.com",
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--expand",
            "companies",
            "--csv-mode",
            "nested",
            "--csv",
            str(csv_file),
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output

    # Read CSV and check nested JSON columns
    with csv_file.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1  # Single row (nested mode)
    row = rows[0]

    # Verify nested JSON columns
    assert "_expand_people" in row
    assert "_expand_companies" in row

    people_data = json.loads(row["_expand_people"])
    companies_data = json.loads(row["_expand_companies"])

    assert len(people_data) == 2
    assert people_data[0]["id"] == 101
    assert people_data[0]["name"] == "Alice Smith"
    assert people_data[1]["id"] == 102
    assert people_data[1]["name"] == "Bob Jones"

    assert len(companies_data) == 1
    assert companies_data[0]["id"] == 201
    assert companies_data[0]["name"] == "Acme Corp"


# ==============================================================================
# Company List Export with --expand people Tests (Phase 2)
# ==============================================================================


def test_company_list_export_expand_people(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test company list export with --expand people."""
    # Mock list metadata (company/organization list)
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Organizations",
                "type": 1,  # organization
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 2,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [{"id": "f1", "name": "Industry", "type": "text", "valueType": None}],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "organization",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 2001, "name": "Acme Corp"},
                        "fields": {"data": {"f1": "Tech"}},
                    },
                    {
                        "id": 1002,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "organization",
                        "createdAt": "2024-01-02T00:00:00Z",
                        "entity": {"id": 2002, "name": "Beta Inc"},
                        "fields": {"data": {"f1": "Finance"}},
                    },
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 organization get for associations (Acme - 2 people)
    respx_mock.get("https://api.affinity.co/organizations/2001").mock(
        return_value=Response(
            200,
            json={
                "id": 2001,
                "name": "Acme Corp",
                "domain": "acme.com",
                "person_ids": [101, 102],
            },
        )
    )
    # Mock V1 organization get for associations (Beta - 1 person)
    respx_mock.get("https://api.affinity.co/organizations/2002").mock(
        return_value=Response(
            200,
            json={
                "id": 2002,
                "name": "Beta Inc",
                "domain": "beta.com",
                "person_ids": [103],
            },
        )
    )

    # Mock person details
    respx_mock.get("https://api.affinity.co/persons/101").mock(
        return_value=Response(
            200,
            json={
                "id": 101,
                "first_name": "Alice",
                "last_name": "Smith",
                "emails": ["alice@acme.com"],
                "type": 1,
            },
        )
    )
    respx_mock.get("https://api.affinity.co/persons/102").mock(
        return_value=Response(
            200,
            json={
                "id": 102,
                "first_name": "Bob",
                "last_name": "Jones",
                "emails": ["bob@acme.com"],
                "type": 1,
            },
        )
    )
    respx_mock.get("https://api.affinity.co/persons/103").mock(
        return_value=Response(
            200,
            json={
                "id": 103,
                "first_name": "Carol",
                "last_name": "White",
                "emails": ["carol@beta.com"],
                "type": 1,
            },
        )
    )

    csv_file = tmp_path / "companies-with-people.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--all",
            "--csv",
            str(csv_file),
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 3  # 2 people for Acme + 1 for Beta

    # Verify entriesProcessed and associationsFetched
    assert payload["data"]["entriesProcessed"] == 2
    assert payload["data"]["associationsFetched"]["people"] == 3

    # Verify CSV content
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 3

        # First entry (Acme), first person (Alice)
        assert rows[0]["listEntryId"] == "1001"
        assert rows[0]["entityId"] == "2001"
        assert rows[0]["entityName"] == "Acme Corp"
        assert rows[0]["expandedType"] == "person"
        assert rows[0]["expandedId"] == "101"
        assert rows[0]["expandedName"] == "Alice Smith"
        assert rows[0]["expandedEmail"] == "alice@acme.com"

        # First entry (Acme), second person (Bob)
        assert rows[1]["listEntryId"] == "1001"
        assert rows[1]["expandedId"] == "102"
        assert rows[1]["expandedName"] == "Bob Jones"

        # Second entry (Beta), first person (Carol)
        assert rows[2]["listEntryId"] == "1002"
        assert rows[2]["entityId"] == "2002"
        assert rows[2]["expandedId"] == "103"
        assert rows[2]["expandedName"] == "Carol White"


def test_company_list_export_expand_people_json(respx_mock: respx.MockRouter) -> None:
    """Test company list export with --expand people produces JSON output."""
    # Mock list metadata
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Organizations",
                "type": 1,  # organization
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "organization",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 2001, "name": "Acme Corp"},
                        "fields": {"data": {}},
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 organization get for associations
    respx_mock.get("https://api.affinity.co/organizations/2001").mock(
        return_value=Response(
            200,
            json={
                "id": 2001,
                "name": "Acme Corp",
                "domain": "acme.com",
                "person_ids": [101],
            },
        )
    )

    # Mock person details
    respx_mock.get("https://api.affinity.co/persons/101").mock(
        return_value=Response(
            200,
            json={
                "id": 101,
                "first_name": "Alice",
                "last_name": "Smith",
                "emails": ["alice@acme.com"],
                "type": 1,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())

    # Check nested arrays
    rows = payload["data"]["rows"]
    assert len(rows) == 1
    assert "people" in rows[0]
    # Companies should NOT be in output since only --expand people was used
    assert "companies" not in rows[0]
    assert len(rows[0]["people"]) == 1
    assert rows[0]["people"][0]["id"] == 101
    assert rows[0]["people"][0]["name"] == "Alice Smith"


# ==============================================================================
# Person List Export with --expand companies Tests (Phase 3)
# ==============================================================================


def test_person_list_export_expand_companies(respx_mock: respx.MockRouter, tmp_path: Path) -> None:
    """Test person list export with --expand companies."""
    # Mock list metadata (person list)
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Contacts",
                "type": 0,  # person
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 2,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [{"id": "f1", "name": "Title", "type": "text", "valueType": None}],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "person",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 101, "firstName": "Alice", "lastName": "Smith"},
                        "fields": {"data": {"f1": "CEO"}},
                    },
                    {
                        "id": 1002,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "person",
                        "createdAt": "2024-01-02T00:00:00Z",
                        "entity": {"id": 102, "firstName": "Bob", "lastName": "Jones"},
                        "fields": {"data": {"f1": "CTO"}},
                    },
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 person get for associations (Alice - 2 companies)
    respx_mock.get("https://api.affinity.co/persons/101").mock(
        return_value=Response(
            200,
            json={
                "id": 101,
                "first_name": "Alice",
                "last_name": "Smith",
                "emails": ["alice@example.com"],
                "organization_ids": [2001, 2002],
            },
        )
    )
    # Mock V1 person get for associations (Bob - 1 company)
    respx_mock.get("https://api.affinity.co/persons/102").mock(
        return_value=Response(
            200,
            json={
                "id": 102,
                "first_name": "Bob",
                "last_name": "Jones",
                "emails": ["bob@example.com"],
                "organization_ids": [2003],
            },
        )
    )

    # Mock V1 organization details
    respx_mock.get("https://api.affinity.co/organizations/2001").mock(
        return_value=Response(
            200,
            json={
                "id": 2001,
                "name": "Acme Corp",
                "domain": "acme.com",
            },
        )
    )
    respx_mock.get("https://api.affinity.co/organizations/2002").mock(
        return_value=Response(
            200,
            json={
                "id": 2002,
                "name": "Beta Inc",
                "domain": "beta.com",
            },
        )
    )
    respx_mock.get("https://api.affinity.co/organizations/2003").mock(
        return_value=Response(
            200,
            json={
                "id": 2003,
                "name": "Gamma Ltd",
                "domain": "gamma.com",
            },
        )
    )

    csv_file = tmp_path / "people-with-companies.csv"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "companies",
            "--all",
            "--csv",
            str(csv_file),
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 3  # 2 companies for Alice + 1 for Bob

    # Verify entriesProcessed and associationsFetched
    assert payload["data"]["entriesProcessed"] == 2
    assert payload["data"]["associationsFetched"]["companies"] == 3

    # Verify CSV content
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 3

        # First entry (Alice), first company (Acme)
        assert rows[0]["listEntryId"] == "1001"
        assert rows[0]["entityId"] == "101"
        assert rows[0]["expandedType"] == "company"
        assert rows[0]["expandedId"] == "2001"
        assert rows[0]["expandedName"] == "Acme Corp"
        assert rows[0]["expandedDomain"] == "acme.com"

        # First entry (Alice), second company (Beta)
        assert rows[1]["listEntryId"] == "1001"
        assert rows[1]["expandedId"] == "2002"
        assert rows[1]["expandedName"] == "Beta Inc"

        # Second entry (Bob), first company (Gamma)
        assert rows[2]["listEntryId"] == "1002"
        assert rows[2]["entityId"] == "102"
        assert rows[2]["expandedId"] == "2003"
        assert rows[2]["expandedName"] == "Gamma Ltd"


def test_person_list_export_expand_companies_json(respx_mock: respx.MockRouter) -> None:
    """Test person list export with --expand companies produces JSON output."""
    # Mock list metadata
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Contacts",
                "type": 0,  # person
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "person",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 101, "firstName": "Alice", "lastName": "Smith"},
                        "fields": {"data": {}},
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 person get for associations
    respx_mock.get("https://api.affinity.co/persons/101").mock(
        return_value=Response(
            200,
            json={
                "id": 101,
                "first_name": "Alice",
                "last_name": "Smith",
                "emails": ["alice@example.com"],
                "organization_ids": [2001],
            },
        )
    )

    # Mock V1 organization details
    respx_mock.get("https://api.affinity.co/organizations/2001").mock(
        return_value=Response(
            200,
            json={
                "id": 2001,
                "name": "Acme Corp",
                "domain": "acme.com",
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "companies",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())

    # Check nested arrays
    rows = payload["data"]["rows"]
    assert len(rows) == 1
    assert "companies" in rows[0]
    # People should NOT be in output since only --expand companies was used
    assert "people" not in rows[0]
    assert len(rows[0]["companies"]) == 1
    assert rows[0]["companies"][0]["id"] == 2001
    assert rows[0]["companies"][0]["name"] == "Acme Corp"
    assert rows[0]["companies"][0]["domain"] == "acme.com"


# =============================================================================
# Phase 5 Tests: --expand-filter and --expand opportunities
# =============================================================================


def test_list_export_expand_filter_requires_expand() -> None:
    """Test --expand-filter without --expand fails with clear error."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "list", "export", "12345", "--expand-filter", "name=Alice", "--all"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert "--expand-filter requires --expand" in payload["error"]["message"]
    assert payload["error"]["type"] == "usage_error"


def test_list_export_expand_opportunities_list_requires_expand_opportunities(
    respx_mock: respx.MockRouter,
) -> None:
    """Test --expand-opportunities-list requires --expand opportunities."""
    # Mock list lookup
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Contacts",
                "type": 0,  # person
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 10,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "companies",  # Using companies, not opportunities
            "--expand-opportunities-list",
            "Pipeline",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    expected_msg = "--expand-opportunities-list requires --expand opportunities"
    assert expected_msg in payload["error"]["message"]
    assert payload["error"]["type"] == "usage_error"


def test_list_export_expand_opportunities_valid_on_person_list(
    respx_mock: respx.MockRouter,
) -> None:
    """Test --expand opportunities is valid on person lists (no error)."""
    # Mock person list
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Contacts",
                "type": 0,  # person
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields endpoint
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(200, json={"fields": []})
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [],  # Empty for this test - just checking validation passes
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "list", "export", "12345", "--expand", "opportunities", "--all"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    # Should not fail with invalid expand error
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["ok"] is True


def test_list_export_expand_opportunities_valid_on_company_list(
    respx_mock: respx.MockRouter,
) -> None:
    """Test --expand opportunities is valid on company lists (no error)."""
    # Mock company list
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Organizations",
                "type": 1,  # organization
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock fields endpoint
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(200, json={"fields": []})
    )

    # Mock list entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [],  # Empty for this test - just checking validation passes
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "list", "export", "12345", "--expand", "opportunities", "--all"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    # Should not fail with invalid expand error
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["ok"] is True


def test_list_export_expand_opportunities_invalid_on_opportunity_list(
    respx_mock: respx.MockRouter,
) -> None:
    """Test --expand opportunities is NOT valid on opportunity lists."""
    # Mock opportunity list
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 10,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "list", "export", "12345", "--expand", "opportunities", "--all"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert payload["ok"] is False
    assert "not valid for opportunity lists" in payload["error"]["message"]
    # Valid values should be people, companies (not opportunities)
    assert "opportunities" not in payload["error"]["details"]["validExpand"]


def test_list_export_expand_opportunities_list_must_be_opportunity_type(
    respx_mock: respx.MockRouter,
) -> None:
    """Test --expand-opportunities-list must reference an opportunity list."""
    # Mock person list (main list)
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Contacts",
                "type": 0,  # person
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock the referenced list as a company list (invalid)
    respx_mock.get("https://api.affinity.co/lists/67890").mock(
        return_value=Response(
            200,
            json={
                "id": 67890,
                "name": "Organizations",
                "type": 1,  # organization - Not opportunity
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 5,
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "opportunities",
            "--expand-opportunities-list",
            "67890",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    payload = json.loads(result.output.strip())
    assert "must reference an opportunity list" in payload["error"]["message"]


def test_list_export_expand_fields_validates_invalid_field(
    respx_mock: respx.MockRouter,
) -> None:
    """Test --expand-fields with invalid field name fails with helpful error."""
    # Mock list metadata (opportunity list so we can expand people)
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 5,
            },
        )
    )

    # Mock list fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock persons fields - return a few valid fields for the error message hint
    respx_mock.get("https://api.affinity.co/v2/persons/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": "field-1001",
                        "name": "Title",
                        "valueType": "text",
                        "type": "global",
                    },
                    {
                        "id": "field-1002",
                        "name": "Department",
                        "valueType": "text",
                        "type": "global",
                    },
                    {
                        "id": "affinity-data-location",
                        "name": "Location",
                        "valueType": "text",
                        "type": "enriched",
                    },
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--expand-fields",
            "InvalidFieldName",
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output.strip())
    assert "Unknown expand field: 'InvalidFieldName'" in payload["error"]["message"]
    assert payload["error"]["type"] == "usage_error"
    # Verify hint includes available fields
    assert "hint" in payload["error"]
    assert "Title" in payload["error"]["hint"] or "Department" in payload["error"]["hint"]


def test_list_export_expand_fields_validates_by_name(
    respx_mock: respx.MockRouter, tmp_path: object
) -> None:
    """Test --expand-fields resolves field names to IDs and validates them."""
    csv_file = Path(tmp_path) / "output.csv"  # type: ignore[arg-type]

    # Mock list metadata (opportunity list so we can expand people)
    respx_mock.get("https://api.affinity.co/lists/12345").mock(
        return_value=Response(
            200,
            json={
                "id": 12345,
                "name": "Pipeline",
                "type": 8,
                "public": False,
                "owner_id": 1,
                "creator_id": 1,
                "list_size": 1,
            },
        )
    )

    # Mock list fields
    respx_mock.get("https://api.affinity.co/v2/lists/12345/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock persons fields - return the field we'll request by name
    respx_mock.get("https://api.affinity.co/v2/persons/fields").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {"id": "field-1001", "name": "Title", "valueType": "text", "type": "global"},
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock entries
    respx_mock.get("https://api.affinity.co/v2/lists/12345/list-entries").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "id": 1001,
                        "listId": 12345,
                        "creatorId": 1,
                        "type": "opportunity",
                        "createdAt": "2024-01-01T00:00:00Z",
                        "entity": {"id": 5001, "name": "Deal"},
                        "fields": {"data": {}},
                    }
                ],
                "pagination": {"nextUrl": None, "prevUrl": None},
            },
        )
    )

    # Mock V1 opportunity for associations
    respx_mock.get("https://api.affinity.co/opportunities/5001").mock(
        return_value=Response(
            200,
            json={
                "id": 5001,
                "name": "Deal",
                "list_id": 12345,
                "person_ids": [2001],
                "organization_ids": [],
            },
        )
    )

    # Mock person get with field value (V2)
    # The V2 API returns fields as a simple dict - the FieldValues model wraps it
    respx_mock.get("https://api.affinity.co/v2/persons/2001").mock(
        return_value=Response(
            200,
            json={
                "id": 2001,
                "firstName": "Alice",
                "lastName": "Smith",
                "primaryEmailAddress": "alice@example.com",
                "fields": {"field-1001": "Engineer"},
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "list",
            "export",
            "12345",
            "--expand",
            "people",
            "--expand-fields",
            "Title",  # Use name, not ID - should be resolved
            "--csv",
            str(csv_file),
            "--all",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["rowsWritten"] == 1

    # Verify CSV has the resolved field column
    assert csv_file.exists()
    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        # The column should use the display name "Title" since header_mode defaults to "names"
        assert "person.Title" in rows[0]
        assert rows[0]["person.Title"] == "Engineer"
