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
