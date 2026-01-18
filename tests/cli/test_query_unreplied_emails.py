"""Tests for query unrepliedEmails expansion.

Tests the unrepliedEmails expansion for listEntries which detects
unreplied incoming emails for each entity.

Related: docs/internal/query-list-export-parity-plan.md
"""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAsyncCheckUnrepliedEmailEntityTypes:
    """Tests for async_check_unreplied_email entity type handling."""

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-001")
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_entity_type(self) -> None:
        """Returns None for unknown entity types."""
        from affinity.cli.interaction_utils import async_check_unreplied_email

        mock_client = MagicMock()

        result = await async_check_unreplied_email(mock_client, "unknown", 123)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-001")
    @pytest.mark.asyncio
    async def test_accepts_person_entity_type(self) -> None:
        """Accepts 'person' entity type string."""
        from affinity.cli.interaction_utils import async_check_unreplied_email

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            # Yield nothing to simulate no emails
            return
            yield  # Make it a generator

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        # Should not raise, should return None (no emails)
        result = await async_check_unreplied_email(mock_client, "person", 123)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-001")
    @pytest.mark.asyncio
    async def test_accepts_company_entity_type(self) -> None:
        """Accepts 'company' entity type string."""
        from affinity.cli.interaction_utils import async_check_unreplied_email

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied_email(mock_client, "company", 456)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-001")
    @pytest.mark.asyncio
    async def test_accepts_opportunity_entity_type(self) -> None:
        """Accepts 'opportunity' entity type string."""
        from affinity.cli.interaction_utils import async_check_unreplied_email

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied_email(mock_client, "opportunity", 789)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-001")
    @pytest.mark.asyncio
    async def test_accepts_v1_integer_person_type(self) -> None:
        """Accepts V1 integer entity type (0 = person)."""
        from affinity.cli.interaction_utils import async_check_unreplied_email

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied_email(mock_client, 0, 123)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-001")
    @pytest.mark.asyncio
    async def test_accepts_v1_integer_company_type(self) -> None:
        """Accepts V1 integer entity type (1 = company)."""
        from affinity.cli.interaction_utils import async_check_unreplied_email

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied_email(mock_client, 1, 456)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-001")
    @pytest.mark.asyncio
    async def test_accepts_organization_entity_type(self) -> None:
        """Accepts 'organization' entity type (V1/V2 variant of company)."""
        from affinity.cli.interaction_utils import async_check_unreplied_email

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied_email(mock_client, "organization", 456)
        assert result is None


class TestUnrepliedEmailsExpansionSchema:
    """Tests for unrepliedEmails expansion schema configuration."""

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-002")
    def test_unreplied_emails_in_expansion_registry(self) -> None:
        """unrepliedEmails is defined in EXPANSION_REGISTRY."""
        from affinity.cli.query.schema import EXPANSION_REGISTRY

        assert "unrepliedEmails" in EXPANSION_REGISTRY

        expansion = EXPANSION_REGISTRY["unrepliedEmails"]
        assert expansion.name == "unrepliedEmails"
        assert "persons" in expansion.supported_entities
        assert "companies" in expansion.supported_entities
        assert "opportunities" in expansion.supported_entities

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-002")
    def test_list_entries_supports_unreplied_emails_expansion(self) -> None:
        """listEntries schema includes unrepliedEmails in supported_expansions."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        list_entries_schema = SCHEMA_REGISTRY["listEntries"]
        assert "unrepliedEmails" in list_entries_schema.supported_expansions

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-002")
    def test_unreplied_emails_does_not_require_refetch(self) -> None:
        """unrepliedEmails expansion does not require entity refetch."""
        from affinity.cli.query.schema import EXPANSION_REGISTRY

        expansion = EXPANSION_REGISTRY["unrepliedEmails"]
        assert expansion.requires_refetch is False


class TestUnrepliedEmailsExpansionExecution:
    """Tests for unrepliedEmails expansion execution in query executor."""

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-003")
    @pytest.mark.asyncio
    async def test_expand_list_entries_handles_unreplied_emails(self) -> None:
        """_expand_list_entries handles unrepliedEmails expansion."""
        from affinity.cli.query.executor import QueryExecutor
        from affinity.cli.query.models import PlanStep
        from affinity.cli.query.schema import EXPANSION_REGISTRY

        # Mock execution context
        class MockExecutionContext:
            records: ClassVar[list[dict[str, Any]]] = [
                {"id": 100, "entityId": 1, "entityType": "person"},
                {"id": 101, "entityId": 2, "entityType": "company"},
            ]

        ctx = MockExecutionContext()
        expansion_def = EXPANSION_REGISTRY["unrepliedEmails"]
        step = PlanStep(
            step_id=1,
            operation="expand",
            description="expand unrepliedEmails",
        )

        # Mock the async_check_unreplied_email function
        with patch("affinity.cli.interaction_utils.async_check_unreplied_email") as mock_check:
            mock_check.return_value = {
                "date": "2026-01-15",
                "daysSince": 3,
                "subject": "Test Email",
            }

            executor = QueryExecutor.__new__(QueryExecutor)
            executor.client = MagicMock()
            executor.rate_limiter = AsyncMock()
            executor.rate_limiter.__aenter__ = AsyncMock()
            executor.rate_limiter.__aexit__ = AsyncMock()
            executor.progress = MagicMock()  # Mock progress reporter

            await executor._expand_list_entries(step, ctx, expansion_def)

        # Verify unrepliedEmails added to records
        assert ctx.records[0].get("unrepliedEmails") is not None
        assert ctx.records[1].get("unrepliedEmails") is not None


class TestQueryWithUnrepliedEmailsExpansion:
    """Integration tests for query with unrepliedEmails expansion."""

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-004")
    def test_query_model_accepts_unreplied_emails_expand(self) -> None:
        """Query model accepts unrepliedEmails in expand field."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "expand": ["unrepliedEmails"],
            }
        )

        assert query.expand is not None
        assert "unrepliedEmails" in query.expand

    @pytest.mark.req("QUERY-UNREPLIED-EMAILS-004")
    def test_query_model_accepts_multiple_expansions(self) -> None:
        """Query model accepts multiple expansions including unrepliedEmails."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "expand": ["interactionDates", "unrepliedEmails"],
            }
        )

        assert query.expand is not None
        assert "interactionDates" in query.expand
        assert "unrepliedEmails" in query.expand
