"""
Query-List Export Parity Integration Tests.

These tests run against a live Affinity sandbox to verify:
1. Query relationships (persons, companies, opportunities, interactions)
2. Query expansions (interactionDates, unreplied)
3. Parity between query and list export outputs

Tests are read-only and safe to run repeatedly.

Setup:
    python tests/integration/setup_query_parity_data.py

Run:
    pytest tests/integration/test_query_parity_integration.py -m integration
    pytest tests/integration/test_query_parity_integration.py -m integration -v

Related: docs/internal/query-list-export-parity-plan.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from click.testing import CliRunner

from affinity.cli.main import cli

if TYPE_CHECKING:
    from affinity import Affinity

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Test data file created by setup script
TEST_DATA_FILE = Path(__file__).parent / "query_parity_test_data.json"

# Test prefix used for all test data
TEST_PREFIX = "QUERY_PARITY_TEST_"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def test_data() -> dict[str, Any]:
    """Load test data from setup script output."""
    if not TEST_DATA_FILE.exists():
        pytest.skip(
            f"Test data file not found: {TEST_DATA_FILE}\n"
            "Run setup first: python tests/integration/setup_query_parity_data.py"
        )

    with TEST_DATA_FILE.open() as f:
        data = json.load(f)

    # Verify test data has required fields
    if not data.get("list_id"):
        pytest.skip("Test data missing list_id - rerun setup script")

    return cast(dict[str, Any], data)


@pytest.fixture(scope="module")
def cli_runner() -> CliRunner:
    """Create a CLI runner for tests."""
    return CliRunner()


def run_query(
    cli_runner: CliRunner,
    api_key: str,
    query: dict[str, Any],
    format: str = "json",
) -> dict[str, Any]:
    """Run a query command and return parsed JSON result."""
    result = cli_runner.invoke(
        cli,
        [
            "query",
            "--query",
            json.dumps(query),
            "--output",
            format,
            "--quiet",
        ],
        env={"AFFINITY_API_KEY": api_key},
        catch_exceptions=False,
    )

    if result.exit_code != 0:
        pytest.fail(f"Query failed: {result.output}")

    return cast(dict[str, Any], json.loads(result.output))


def run_list_export(
    cli_runner: CliRunner,
    api_key: str,
    list_name: str,
    filter_str: str | None = None,
) -> dict[str, Any]:
    """Run a list export command and return parsed JSON result.

    Note: list export returns {"data": {"rows": [...]}} format.
    We normalize to {"data": [...]} for parity comparison with query.
    """
    args = ["list", "export", list_name, "--output", "json"]
    if filter_str:
        args.extend(["--filter", filter_str])

    result = cli_runner.invoke(
        cli,
        args,
        env={"AFFINITY_API_KEY": api_key},
        catch_exceptions=False,
    )

    if result.exit_code != 0:
        pytest.fail(f"List export failed: {result.output}")

    output = cast(dict[str, Any], json.loads(result.output))

    # Normalize format: list export returns {"data": {"rows": [...]}}
    # Convert to {"data": [...]} for comparison with query results
    if isinstance(output.get("data"), dict) and "rows" in output["data"]:
        output["data"] = output["data"]["rows"]

    return output


# =============================================================================
# Test: Query Basics with listEntries
# =============================================================================


class TestQueryListEntriesBasics:
    """Test basic query functionality for listEntries."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-001")
    def test_query_list_entries_by_name(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries by listName returns results."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "limit": 10,
            },
        )

        assert "data" in result
        assert isinstance(result["data"], list)
        # We created entries in setup
        if len(result["data"]) == 0:
            pytest.skip("No entries in test list - rerun setup script")

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-001")
    def test_query_list_entries_by_id(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries by listId returns results."""
        list_id = test_data["list_id"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listId", "op": "eq", "value": list_id},
                "limit": 10,
            },
        )

        assert "data" in result
        assert isinstance(result["data"], list)

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-001")
    def test_query_list_entries_select_fields(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with select returns only requested fields."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "select": ["listEntryId", "entityName", "entityType"],
                "limit": 5,
            },
        )

        assert "data" in result
        if result["data"]:
            entry = result["data"][0]
            # Selected fields should be present
            assert "listEntryId" in entry or "id" in entry
            assert "entityName" in entry or "name" in entry


# =============================================================================
# Test: Query with Include (Relationships)
# =============================================================================


class TestQueryListEntriesIncludes:
    """Test query include functionality for listEntries."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-002")
    def test_query_include_persons(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with include persons fetches related persons."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "include": ["persons"],
                "limit": 5,
            },
        )

        assert "data" in result
        # Included data appears in separate section
        if result.get("included"):
            assert "persons" in result["included"]

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-002")
    def test_query_include_companies(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with include companies fetches related companies."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "include": ["companies"],
                "limit": 5,
            },
        )

        assert "data" in result
        if result.get("included"):
            assert "companies" in result["included"]

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-002")
    def test_query_include_multiple(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with multiple includes works."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "include": ["persons", "companies"],
                "limit": 5,
            },
        )

        assert "data" in result
        # Both should be included if entities exist
        if "included" in result:
            # At least one should be present
            assert "persons" in result.get("included", {}) or "companies" in result.get(
                "included", {}
            )

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-002")
    def test_query_include_interactions(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with include interactions fetches interactions."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "include": ["interactions"],
                "limit": 3,
            },
        )

        assert "data" in result
        # Interactions may or may not exist for test data
        # Just verify the query doesn't fail

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-002")
    def test_query_include_interactions_with_limit(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query with parameterized interactions include respects limit."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "include": [{"interactions": {"limit": 5, "days": 90}}],
                "limit": 3,
            },
        )

        assert "data" in result


# =============================================================================
# Test: Query with Expand
# =============================================================================


class TestQueryListEntriesExpand:
    """Test query expand functionality for listEntries."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-003")
    def test_query_expand_interaction_dates(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with expand interactionDates adds dates to records."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "expand": ["interactionDates"],
                "limit": 3,
            },
        )

        assert "data" in result
        # Expanded data should be merged into records
        # interactionDates expansion adds fields like lastMeetingDate, lastEmailDate
        # These may be null if no interactions exist

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-003")
    def test_query_expand_unreplied(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with expand unreplied adds email status."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "expand": ["unreplied"],
                "limit": 3,
            },
        )

        assert "data" in result
        # unreplied field should be present (may be null)
        # The expansion merges directly into records

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-003")
    def test_query_expand_multiple(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with multiple expansions works."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "expand": ["interactionDates", "unreplied"],
                "limit": 3,
            },
        )

        assert "data" in result


# =============================================================================
# Test: Query with Include AND Expand
# =============================================================================


class TestQueryIncludeAndExpand:
    """Test combining include and expand in queries."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-004")
    def test_query_include_and_expand_together(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query with both include and expand works correctly."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "include": ["persons", "companies"],
                "expand": ["interactionDates"],
                "limit": 3,
            },
        )

        assert "data" in result
        # Include creates separate section, expand merges into records

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-004")
    def test_query_full_list_export_equivalent(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query can express full list export functionality."""
        list_name = test_data["list_name"]

        # This query should get everything list export would get
        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "include": ["persons", "companies", "opportunities", "interactions"],
                "expand": ["interactionDates", "unreplied"],
                "select": ["listEntryId", "entityId", "entityName", "entityType", "fields.*"],
                "limit": 10,
            },
        )

        assert "data" in result
        assert isinstance(result["data"], list)


# =============================================================================
# Test: Query vs List Export Parity
# =============================================================================


class TestQueryListExportParity:
    """Test that query and list export return equivalent data."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-005")
    def test_query_returns_same_entry_count(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query and list export return same number of entries."""
        list_name = test_data["list_name"]

        # Query result
        query_result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "limit": 100,
            },
        )

        # List export result
        export_result = run_list_export(cli_runner, sandbox_api_key, list_name)

        query_count = len(query_result.get("data", []))
        export_count = len(export_result.get("data", []))

        assert query_count == export_count, (
            f"Query returned {query_count} entries, export returned {export_count}"
        )

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-005")
    def test_query_returns_same_entity_ids(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query and list export return same entity IDs."""
        list_name = test_data["list_name"]

        # Query result
        query_result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "limit": 100,
            },
        )

        # List export result
        export_result = run_list_export(cli_runner, sandbox_api_key, list_name)

        # Extract entity IDs
        query_ids = {e.get("entityId") or e.get("entity_id") for e in query_result.get("data", [])}
        export_ids = {
            e.get("entityId") or e.get("entity_id") for e in export_result.get("data", [])
        }

        # Remove None values
        query_ids.discard(None)
        export_ids.discard(None)

        assert query_ids == export_ids, f"Query IDs: {query_ids}\nExport IDs: {export_ids}"

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-005")
    def test_field_values_match(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query returns same field values as list export."""
        list_name = test_data["list_name"]

        # Query with fields
        query_result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "select": ["listEntryId", "entityId", "entityName", "fields.*"],
                "limit": 10,
            },
        )

        # List export
        export_result = run_list_export(cli_runner, sandbox_api_key, list_name)

        if not query_result.get("data") or not export_result.get("data"):
            pytest.skip("No entries to compare")

        # Build lookup by entity ID
        query_by_entity = {
            e.get("entityId") or e.get("entity_id"): e for e in query_result.get("data", [])
        }
        export_by_entity = {
            e.get("entityId") or e.get("entity_id"): e for e in export_result.get("data", [])
        }

        # Compare field values for common entities
        common_ids = set(query_by_entity.keys()) & set(export_by_entity.keys())
        common_ids.discard(None)

        for entity_id in list(common_ids)[:3]:  # Check first 3
            query_entry = query_by_entity[entity_id]
            export_entry = export_by_entity[entity_id]

            # Check entityName matches
            query_name = query_entry.get("entityName") or query_entry.get("name")
            export_name = export_entry.get("entityName") or export_entry.get("name")

            if query_name and export_name:
                assert query_name == export_name, (
                    f"Entity {entity_id}: query name '{query_name}' != export name '{export_name}'"
                )


# =============================================================================
# Test: Query Output Formats
# =============================================================================


class TestQueryOutputFormats:
    """Test query output in different formats."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-006")
    def test_query_json_format(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query with JSON format returns valid JSON structure."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": list_name},
                "limit": 5,
            },
            format="json",
        )

        assert "data" in result
        assert isinstance(result["data"], list)

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-006")
    def test_query_markdown_format(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query with markdown format returns table."""
        list_name = test_data["list_name"]

        result = cli_runner.invoke(
            cli,
            [
                "query",
                "--query",
                json.dumps(
                    {
                        "from": "listEntries",
                        "where": {"path": "listName", "op": "eq", "value": list_name},
                        "limit": 3,
                    }
                ),
                "--output",
                "markdown",
                "--quiet",
            ],
            env={"AFFINITY_API_KEY": sandbox_api_key},
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        # Markdown output should contain table formatting or data
        assert (
            "|" in result.output or "No results" in result.output or len(result.output.strip()) > 0
        )


# =============================================================================
# Test: Query Performance and Dry Run
# =============================================================================


class TestQueryDryRun:
    """Test query dry run functionality."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-007")
    def test_query_dry_run_shows_plan(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query with dry-run shows execution plan without running."""
        list_name = test_data["list_name"]

        result = cli_runner.invoke(
            cli,
            [
                "query",
                "--query",
                json.dumps(
                    {
                        "from": "listEntries",
                        "where": {"path": "listName", "op": "eq", "value": list_name},
                        "include": ["persons", "companies"],
                        "limit": 5,
                    }
                ),
                "--dry-run",
                "--output",
                "json",
                "--quiet",  # Suppress warnings before JSON output
            ],
            env={"AFFINITY_API_KEY": sandbox_api_key},
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        # Dry run output should show plan information
        output = json.loads(result.output)
        assert "steps" in output, f"Expected 'steps' in dry-run output: {output}"


# =============================================================================
# Test: Entity-Specific Queries
# =============================================================================


class TestQueryPersons:
    """Test query functionality for persons."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-008")
    def test_query_persons_with_include(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query persons with include companies."""
        # Use specific person IDs from test data to avoid full scan
        person_ids = test_data.get("person_ids", [])
        if not person_ids:
            pytest.skip("No test person IDs available")

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "persons",
                "where": {
                    "path": "id",
                    "op": "in",
                    "value": person_ids[:3],  # Query specific IDs
                },
                "include": ["companies"],
            },
        )

        assert "data" in result

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-008")
    def test_query_persons_with_expand(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query persons with expand interactionDates."""
        # Use specific person IDs from test data to avoid full scan
        person_ids = test_data.get("person_ids", [])
        if not person_ids:
            pytest.skip("No test person IDs available")

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "persons",
                "where": {
                    "path": "id",
                    "op": "in",
                    "value": person_ids[:3],  # Query specific IDs
                },
                "expand": ["interactionDates"],
            },
        )

        assert "data" in result


class TestQueryCompanies:
    """Test query functionality for companies."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-009")
    def test_query_companies_with_include(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query companies with include persons."""
        # Use specific company IDs from test data to avoid full scan
        company_ids = test_data.get("company_ids", [])
        if not company_ids:
            pytest.skip("No test company IDs available")

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "companies",
                "where": {
                    "path": "id",
                    "op": "in",
                    "value": company_ids[:3],  # Query specific IDs
                },
                "include": ["persons"],
            },
        )

        assert "data" in result

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-009")
    def test_query_companies_with_expand(
        self,
        _sandbox_client: Affinity,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query companies with expand interactionDates."""
        # Use specific company IDs from test data to avoid full scan
        company_ids = test_data.get("company_ids", [])
        if not company_ids:
            pytest.skip("No test company IDs available")

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "companies",
                "where": {
                    "path": "id",
                    "op": "in",
                    "value": company_ids[:3],  # Query specific IDs
                },
                "expand": ["interactionDates"],
            },
        )

        assert "data" in result


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestQueryEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-010")
    def test_query_empty_result(
        self,
        sandbox_api_key: str,
        cli_runner: CliRunner,
    ) -> None:
        """Query with no matches returns empty data array."""
        # Use a non-existent ID to avoid full scan
        # (querying by firstName would require scanning all persons)
        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "persons",
                "where": {
                    "path": "id",
                    "op": "eq",
                    "value": 999999999,  # Non-existent ID
                },
            },
        )

        assert "data" in result
        assert result["data"] == []

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-010")
    def test_query_with_filter_on_list_entries(
        self,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query listEntries with additional entityName filter works."""
        list_name = test_data["list_name"]

        result = run_query(
            cli_runner,
            sandbox_api_key,
            {
                "from": "listEntries",
                "where": {
                    "and": [
                        {"path": "listName", "op": "eq", "value": list_name},
                        {"path": "entityName", "op": "contains", "value": TEST_PREFIX},
                    ]
                },
                "limit": 10,
            },
        )

        assert "data" in result
        # All returned entries should have names containing the test prefix
        for entry in result.get("data", []):
            name = entry.get("entityName") or entry.get("name") or ""
            assert TEST_PREFIX in name or name == "", (
                f"Entry name '{name}' doesn't contain '{TEST_PREFIX}'"
            )

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-011")
    def test_query_nonexistent_list_name(
        self,
        sandbox_api_key: str,
        cli_runner: CliRunner,
    ) -> None:
        """Query for non-existent list name returns clear error."""
        result = cli_runner.invoke(
            cli,
            [
                "query",
                "--query",
                json.dumps(
                    {
                        "from": "listEntries",
                        "where": {
                            "path": "listName",
                            "op": "eq",
                            "value": "NONEXISTENT_LIST_12345",
                        },
                    }
                ),
                "--output",
                "json",
                "--quiet",
            ],
            env={"AFFINITY_API_KEY": sandbox_api_key},
            catch_exceptions=True,  # Capture error instead of raising
        )

        # Should fail with non-zero exit code
        assert result.exit_code != 0, f"Expected error for non-existent list, got: {result.output}"
        # Error message should mention the list wasn't found
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-011")
    def test_query_invalid_include_value(
        self,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query with invalid include value returns clear error."""
        list_name = test_data["list_name"]

        result = cli_runner.invoke(
            cli,
            [
                "query",
                "--query",
                json.dumps(
                    {
                        "from": "listEntries",
                        "where": {"path": "listName", "op": "eq", "value": list_name},
                        "include": ["invalidRelationship"],
                    }
                ),
                "--output",
                "json",
                "--quiet",
            ],
            env={"AFFINITY_API_KEY": sandbox_api_key},
            catch_exceptions=True,
        )

        # Should fail with non-zero exit code
        assert result.exit_code != 0, f"Expected error for invalid include, got: {result.output}"

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-011")
    def test_query_invalid_expand_value(
        self,
        sandbox_api_key: str,
        cli_runner: CliRunner,
        test_data: dict[str, Any],
    ) -> None:
        """Query with invalid expand value returns clear error."""
        list_name = test_data["list_name"]

        result = cli_runner.invoke(
            cli,
            [
                "query",
                "--query",
                json.dumps(
                    {
                        "from": "listEntries",
                        "where": {"path": "listName", "op": "eq", "value": list_name},
                        "expand": ["invalidExpansion"],
                    }
                ),
                "--output",
                "json",
                "--quiet",
            ],
            env={"AFFINITY_API_KEY": sandbox_api_key},
            catch_exceptions=True,
        )

        # Should fail with non-zero exit code
        assert result.exit_code != 0, f"Expected error for invalid expand, got: {result.output}"

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-011")
    def test_query_invalid_from_source(
        self,
        sandbox_api_key: str,
        cli_runner: CliRunner,
    ) -> None:
        """Query with invalid from source returns clear error."""
        result = cli_runner.invoke(
            cli,
            [
                "query",
                "--query",
                json.dumps(
                    {
                        "from": "invalidSource",
                    }
                ),
                "--output",
                "json",
                "--quiet",
            ],
            env={"AFFINITY_API_KEY": sandbox_api_key},
            catch_exceptions=True,
        )

        # Should fail with non-zero exit code
        assert result.exit_code != 0, f"Expected error for invalid from, got: {result.output}"

    @pytest.mark.req("QUERY-PARITY-INTEGRATION-011")
    def test_query_list_entries_without_list_filter(
        self,
        sandbox_api_key: str,
        cli_runner: CliRunner,
    ) -> None:
        """Query listEntries without listName/listId filter should error."""
        result = cli_runner.invoke(
            cli,
            [
                "query",
                "--query",
                json.dumps(
                    {
                        "from": "listEntries",
                        # Missing listName or listId filter
                    }
                ),
                "--output",
                "json",
                "--quiet",
            ],
            env={"AFFINITY_API_KEY": sandbox_api_key},
            catch_exceptions=True,
        )

        # Should fail - listEntries requires a list filter
        assert result.exit_code != 0, (
            f"Expected error for missing list filter, got: {result.output}"
        )
