"""Integration tests for query expand: ["interactionDates"].

Tests the query language support for expanding interaction date summaries on
persons, companies, and listEntries.
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from affinity.cli.query.exceptions import QueryValidationError
from affinity.cli.query.parser import parse_query

# ==============================================================================
# Parser Tests - Validation of expand clause
# ==============================================================================


class TestQueryExpandParsing:
    """Test parsing of expand clause in queries."""

    @pytest.mark.req("QUERY-EXPAND-001")
    def test_expand_interaction_dates_for_persons_accepted(self) -> None:
        """expand: ["interactionDates"] should be accepted for persons."""
        result = parse_query(
            {
                "from": "persons",
                "expand": ["interactionDates"],
                "limit": 10,
            }
        )
        assert result.query.from_ == "persons"
        assert result.query.expand == ["interactionDates"]

    @pytest.mark.req("QUERY-EXPAND-001")
    def test_expand_interaction_dates_for_companies_accepted(self) -> None:
        """expand: ["interactionDates"] should be accepted for companies."""
        result = parse_query(
            {
                "from": "companies",
                "expand": ["interactionDates"],
                "limit": 10,
            }
        )
        assert result.query.from_ == "companies"
        assert result.query.expand == ["interactionDates"]

    @pytest.mark.req("QUERY-EXPAND-001")
    def test_expand_interaction_dates_for_list_entries_accepted(self) -> None:
        """expand: ["interactionDates"] should be accepted for listEntries."""
        result = parse_query(
            {
                "from": "listEntries",
                "where": {"path": "listId", "op": "eq", "value": 123},
                "expand": ["interactionDates"],
                "limit": 10,
            }
        )
        assert result.query.from_ == "listEntries"
        assert result.query.expand == ["interactionDates"]

    @pytest.mark.req("QUERY-EXPAND-002")
    def test_expand_invalid_name_rejected(self) -> None:
        """Invalid expand names should be rejected."""
        with pytest.raises(QueryValidationError, match="Unknown expansion"):
            parse_query(
                {
                    "from": "persons",
                    "expand": ["invalidExpansion"],
                    "limit": 10,
                }
            )

    @pytest.mark.req("QUERY-EXPAND-002")
    def test_expand_unsupported_entity_rejected(self) -> None:
        """expand should be rejected for unsupported entities."""
        with pytest.raises(QueryValidationError, match="not supported for"):
            parse_query(
                {
                    "from": "opportunities",
                    "expand": ["interactionDates"],
                    "limit": 10,
                }
            )


# ==============================================================================
# Dry-Run Tests - Verify planning without execution
# ==============================================================================


class TestQueryExpandDryRun:
    """Test dry-run output for queries with expand."""

    @pytest.fixture
    def cli_context(self):
        """Create mock CLI context."""
        from unittest.mock import MagicMock

        from affinity.cli.context import CLIContext

        ctx = MagicMock(spec=CLIContext)
        ctx.output = "json"
        ctx.quiet = False
        ctx.verbosity = 0
        return ctx

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    def _extract_json(self, output: str) -> dict:
        """Extract JSON object from output."""
        start = output.find("{")
        if start == -1:
            raise ValueError(f"No JSON object found in output: {output}")
        depth = 0
        for i, char in enumerate(output[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(output[start : i + 1])
        raise ValueError(f"Unbalanced JSON in output: {output}")

    @pytest.mark.req("QUERY-EXPAND-003")
    def test_dry_run_shows_expansion_in_plan(self, runner, cli_context) -> None:
        """Dry run should show expansion step in the execution plan."""
        from affinity.cli.commands.query_cmd import query_cmd

        query = '{"from": "persons", "expand": ["interactionDates"], "limit": 5}'

        result = runner.invoke(
            query_cmd,
            ["--query", query, "--dry-run"],
            obj=cli_context,
        )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        output = self._extract_json(result.output)
        # The query should be in the output
        assert output["query"]["from"] == "persons"
        # Expansion should appear as a step in the execution plan
        expand_steps = [s for s in output["steps"] if s["operation"] == "expand"]
        assert len(expand_steps) == 1
        assert "interactionDates" in expand_steps[0]["description"]

    @pytest.mark.req("QUERY-EXPAND-003")
    def test_dry_run_expansion_for_companies(self, runner, cli_context) -> None:
        """Dry run should show expansion step for companies."""
        from affinity.cli.commands.query_cmd import query_cmd

        query = '{"from": "companies", "expand": ["interactionDates"], "limit": 3}'

        result = runner.invoke(
            query_cmd,
            ["--query", query, "--dry-run"],
            obj=cli_context,
        )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        output = self._extract_json(result.output)
        assert output["query"]["from"] == "companies"
        # Expansion should appear as a step
        expand_steps = [s for s in output["steps"] if s["operation"] == "expand"]
        assert len(expand_steps) == 1
        assert "interactionDates" in expand_steps[0]["description"]

    @pytest.mark.req("QUERY-EXPAND-003")
    def test_dry_run_expansion_for_list_entries(self, runner, cli_context) -> None:
        """Dry run should show expansion step for listEntries."""
        from affinity.cli.commands.query_cmd import query_cmd

        query = json.dumps(
            {
                "from": "listEntries",
                "where": {"path": "listId", "op": "eq", "value": 123},
                "expand": ["interactionDates"],
                "limit": 5,
            }
        )

        result = runner.invoke(
            query_cmd,
            ["--query", query, "--dry-run"],
            obj=cli_context,
        )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        output = self._extract_json(result.output)
        assert output["query"]["from"] == "listEntries"
        # Expansion should appear as a step
        expand_steps = [s for s in output["steps"] if s["operation"] == "expand"]
        assert len(expand_steps) == 1
        assert "interactionDates" in expand_steps[0]["description"]


# ==============================================================================
# Schema Registry Tests
# ==============================================================================


class TestExpandSchemaRegistry:
    """Test that schema registry correctly defines expansion support."""

    def test_persons_supports_interaction_dates(self) -> None:
        """Persons entity should support interactionDates expansion."""
        from affinity.cli.query.schema import get_entity_schema

        schema = get_entity_schema("persons")
        assert schema is not None
        assert "interactionDates" in schema.supported_expansions

    def test_companies_supports_interaction_dates(self) -> None:
        """Companies entity should support interactionDates expansion."""
        from affinity.cli.query.schema import get_entity_schema

        schema = get_entity_schema("companies")
        assert schema is not None
        assert "interactionDates" in schema.supported_expansions

    def test_list_entries_supports_interaction_dates(self) -> None:
        """ListEntries entity should support interactionDates expansion."""
        from affinity.cli.query.schema import get_entity_schema

        schema = get_entity_schema("listEntries")
        assert schema is not None
        assert "interactionDates" in schema.supported_expansions

    def test_opportunities_does_not_support_expansion(self) -> None:
        """Opportunities entity should NOT support expansion."""
        from affinity.cli.query.schema import get_entity_schema

        schema = get_entity_schema("opportunities")
        assert schema is not None
        assert len(schema.supported_expansions) == 0

    def test_expansion_registry_has_interaction_dates(self) -> None:
        """EXPANSION_REGISTRY should have interactionDates defined."""
        from affinity.cli.query.schema import EXPANSION_REGISTRY

        assert "interactionDates" in EXPANSION_REGISTRY
        expansion = EXPANSION_REGISTRY["interactionDates"]
        assert expansion.name == "interactionDates"
        assert expansion.fetch_params["with_interaction_dates"] is True
        assert expansion.fetch_params["with_interaction_persons"] is True


# ==============================================================================
# Executor Tests - Streaming path with expand
# ==============================================================================


class TestStreamingPathWithExpand:
    """Test that expand works correctly in streaming execution path.

    The streaming path is used when:
    - Query has limit (or explicit --max-records)
    - No sort/aggregate/groupBy operations

    This test ensures expand steps are executed after streaming completes.
    Regression test for bug where expand was skipped in streaming path.
    """

    @pytest.mark.asyncio
    @pytest.mark.req("QUERY-EXPAND-004")
    async def test_streaming_path_executes_expand_step(self) -> None:
        """Expand should be executed even when streaming mode is used.

        This tests the fix for the bug where streaming path only handled
        'include' steps but skipped 'expand' steps.
        """
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, MagicMock

        from affinity.cli.query.executor import QueryExecutor
        from affinity.cli.query.parser import parse_query
        from affinity.cli.query.planner import create_planner
        from affinity.models.entities import InteractionDates, Person

        # Create a query that will use streaming (has limit, no sort/aggregate)
        query_dict = {
            "from": "persons",
            "expand": ["interactionDates"],
            "limit": 2,
        }
        parse_result = parse_query(query_dict)
        planner = create_planner()
        plan = planner.plan(parse_result.query)

        # Mock person data
        mock_person = MagicMock(spec=Person)
        mock_person.id = 123
        mock_person.first_name = "Test"
        mock_person.last_name = "User"
        mock_person.primary_email_address = "test@example.com"
        mock_person.model_dump = MagicMock(
            return_value={
                "id": 123,
                "firstName": "Test",
                "lastName": "User",
                "primaryEmailAddress": "test@example.com",
                "type": "external",
            }
        )

        # Mock person with interaction dates (for expand step)
        mock_interaction_dates = MagicMock(spec=InteractionDates)
        mock_interaction_dates.last_event_date = datetime(2026, 1, 10, tzinfo=timezone.utc)
        mock_interaction_dates.next_event_date = None
        mock_interaction_dates.last_email_date = datetime(2026, 1, 8, tzinfo=timezone.utc)
        mock_interaction_dates.last_interaction_date = datetime(2026, 1, 10, tzinfo=timezone.utc)

        mock_person_expanded = MagicMock(spec=Person)
        mock_person_expanded.interaction_dates = mock_interaction_dates
        mock_person_expanded.interactions = {"last_event": {"person_ids": [456]}}
        mock_person_expanded.full_name = "Test User"

        # Mock the team member lookup
        mock_team_member = MagicMock(spec=Person)
        mock_team_member.full_name = "Team Member"

        # Create mock async client
        mock_client = AsyncMock()
        mock_client.whoami = AsyncMock()

        # Mock persons service for streaming (all().pages())
        mock_page = MagicMock()
        mock_page.data = [mock_person]

        async def mock_pages():
            yield mock_page

        mock_persons_all = MagicMock()
        mock_persons_all.pages = mock_pages
        mock_client.persons.all = MagicMock(return_value=mock_persons_all)

        # Mock persons.get for expand step (returns person with interaction dates)
        # AND for name resolution
        async def mock_get(_person_id, **kwargs):
            if kwargs.get("with_interaction_dates"):
                return mock_person_expanded
            return mock_team_member

        mock_client.persons.get = mock_get

        # Create executor and run
        executor = QueryExecutor(
            client=mock_client,
            max_records=100,
            concurrency=1,
        )

        query_result = await executor.execute(plan)

        # Verify expand was executed - records should have interactionDates
        assert len(query_result.data) == 1
        record = query_result.data[0]
        assert "interactionDates" in record, (
            "Expand step was not executed - interactionDates missing from record. "
            "This indicates streaming path may be skipping expand steps."
        )
        assert record["interactionDates"] is not None
        assert "lastMeeting" in record["interactionDates"]
        assert "teamMemberNames" in record["interactionDates"]["lastMeeting"]
        assert record["interactionDates"]["lastMeeting"]["teamMemberNames"] == ["Team Member"]
