"""Additional tests for CLI company commands to improve coverage."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

try:
    import respx
except ModuleNotFoundError:
    respx = None  # type: ignore[assignment]

from click.testing import CliRunner
from httpx import Response

from affinity.cli.main import cli

if respx is None:
    pytest.skip("respx is not installed", allow_module_level=True)


class TestCompanyLs:
    """Tests for company ls command."""

    def test_ls_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic company ls should work."""
        respx_mock.get("https://api.affinity.co/v2/companies").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "name": "Acme Corp", "domain": "acme.com"},
                    ],
                    "pagination": {"nextUrl": None},
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "ls"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_with_filter(self, respx_mock: respx.MockRouter) -> None:
        """Company ls with filter parameter."""
        respx_mock.get("https://api.affinity.co/v2/companies").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "name": "Acme Corp", "domain": "acme.com"},
                    ],
                    "pagination": {"nextUrl": None},
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "ls", "--filter", "domain:acme.com"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_with_max_results(self, respx_mock: respx.MockRouter) -> None:
        """Company ls with --max-results should limit output."""
        respx_mock.get("https://api.affinity.co/v2/companies").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {"id": 1, "name": "Acme Corp", "domain": "acme.com"},
                        {"id": 2, "name": "Beta Inc", "domain": "beta.com"},
                        {"id": 3, "name": "Gamma LLC", "domain": "gamma.com"},
                    ],
                    "pagination": {"nextUrl": "https://api.affinity.co/v2/companies?cursor=next"},
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "ls", "--max-results", "2"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0
        payload = json.loads(result.output.strip())
        assert len(payload["data"]["companies"]) <= 2


class TestCompanyCreate:
    """Tests for company create command."""

    def test_create_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic company create should work."""
        respx_mock.post("https://api.affinity.co/organizations").mock(
            return_value=Response(
                200,
                json={
                    "id": 123,
                    "name": "New Company",
                    "domain": "new.com",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "company",
                "create",
                "--name",
                "New Company",
                "--domain",
                "new.com",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_create_with_person_ids(self, respx_mock: respx.MockRouter) -> None:
        """Company create with associated person IDs."""
        respx_mock.post("https://api.affinity.co/organizations").mock(
            return_value=Response(
                200,
                json={
                    "id": 456,
                    "name": "New Company",
                    "domain": "new.com",
                    "person_ids": [100, 200],
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "company",
                "create",
                "--name",
                "New Company",
                "--person-id",
                "100",
                "--person-id",
                "200",
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestCompanyUpdate:
    """Tests for company update command."""

    def test_update_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic company update should work."""
        respx_mock.put("https://api.affinity.co/organizations/123").mock(
            return_value=Response(
                200,
                json={
                    "id": 123,
                    "name": "Updated Company",
                    "domain": "updated.com",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "update", "123", "--name", "Updated Company"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_update_no_fields_raises(self) -> None:
        """Update with no fields should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "update", "123"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2


class TestCompanyDelete:
    """Tests for company delete command."""

    def test_delete_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic company delete should work."""
        respx_mock.delete("https://api.affinity.co/organizations/123").mock(
            return_value=Response(200, json={"success": True})
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "delete", "123", "--yes"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestCompanyMerge:
    """Tests for company merge command."""

    def test_merge_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic company merge should work."""
        # Merge uses V2 /company-merges endpoint
        respx_mock.post("https://api.affinity.co/v2/company-merges").mock(
            return_value=Response(
                200,
                json={
                    "taskUrl": "https://api.affinity.co/v2/tasks/123",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "--beta", "company", "merge", "100", "101"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestCompanyLsWithQuery:
    """Tests for company ls with --query option."""

    def test_ls_with_query(self, respx_mock: respx.MockRouter) -> None:
        """Company ls with --query should use V1 search."""
        respx_mock.get("https://api.affinity.co/organizations").mock(
            return_value=Response(
                200,
                json={
                    "organizations": [
                        {"id": 1, "name": "Acme Corp", "domain": "acme.com"},
                    ],
                    "next_page_token": None,
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "ls", "--query", "acme"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_query_with_filter_fails(self) -> None:
        """Company ls with both --query and --filter should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "ls", "--query", "acme", "--filter", "domain:x"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2
