"""Additional tests for CLI opportunity commands to improve coverage."""

from __future__ import annotations

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


class TestOpportunityLs:
    """Tests for opportunity ls command."""

    def test_ls_with_query(self, respx_mock: respx.MockRouter) -> None:
        """Opportunity ls with --query parameter uses V1 search."""
        respx_mock.get("https://api.affinity.co/opportunities").mock(
            return_value=Response(
                200,
                json={
                    "opportunities": [
                        {"id": 1, "name": "Series A", "list_entries": []},
                    ],
                    "next_page_token": None,
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "opportunity", "ls", "--query", "Series A"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_with_query_and_all(self, respx_mock: respx.MockRouter) -> None:
        """Opportunity ls with --query and --all fetches all pages."""
        respx_mock.get("https://api.affinity.co/opportunities").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "opportunities": [{"id": 1, "name": "Deal A", "list_entries": []}],
                        "next_page_token": "page2",
                    },
                ),
                Response(
                    200,
                    json={
                        "opportunities": [{"id": 2, "name": "Deal B", "list_entries": []}],
                        "next_page_token": None,
                    },
                ),
            ]
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "opportunity", "ls", "--query", "Deal", "--all"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_with_query_and_max_results(self, respx_mock: respx.MockRouter) -> None:
        """Opportunity ls with --query and --max-results limits output."""
        respx_mock.get("https://api.affinity.co/opportunities").mock(
            return_value=Response(
                200,
                json={
                    "opportunities": [
                        {"id": 1, "name": "Deal A", "list_entries": []},
                        {"id": 2, "name": "Deal B", "list_entries": []},
                        {"id": 3, "name": "Deal C", "list_entries": []},
                    ],
                    "next_page_token": "more",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "opportunity", "ls", "--query", "Deal", "--max-results", "2"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestOpportunityUpdate:
    """Tests for opportunity update command."""

    def test_update_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic opportunity update should work."""
        respx_mock.put("https://api.affinity.co/opportunities/123").mock(
            return_value=Response(
                200,
                json={
                    "id": 123,
                    "name": "Updated Deal",
                    "list_entries": [],
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "opportunity", "update", "123", "--name", "Updated Deal"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_update_no_fields_raises(self) -> None:
        """Update with no fields should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "opportunity", "update", "123"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2


class TestOpportunityDelete:
    """Tests for opportunity delete command."""

    def test_delete_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic opportunity delete should work."""
        respx_mock.delete("https://api.affinity.co/opportunities/123").mock(
            return_value=Response(200, json={"success": True})
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "opportunity", "delete", "123", "--yes"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0
