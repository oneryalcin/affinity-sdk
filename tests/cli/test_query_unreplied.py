"""Tests for query unreplied expansion.

Tests the unreplied expansion for listEntries which detects
unreplied incoming messages (email/chat) for each entity.

Related: docs/internal/query-list-export-parity-plan.md
"""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAsyncCheckUnrepliedEntityTypes:
    """Tests for async_check_unreplied entity type handling."""

    @pytest.mark.req("QUERY-UNREPLIED-001")
    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_entity_type(self) -> None:
        """Returns None for unknown entity types."""
        from affinity.cli.interaction_utils import async_check_unreplied

        mock_client = MagicMock()

        result = await async_check_unreplied(mock_client, "unknown", 123)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-001")
    @pytest.mark.asyncio
    async def test_accepts_person_entity_type(self) -> None:
        """Accepts 'person' entity type string."""
        from affinity.cli.interaction_utils import async_check_unreplied

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            # Yield nothing to simulate no messages
            return
            yield  # Make it a generator

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        # Should not raise, should return None (no messages)
        result = await async_check_unreplied(mock_client, "person", 123)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-001")
    @pytest.mark.asyncio
    async def test_accepts_company_entity_type(self) -> None:
        """Accepts 'company' entity type string."""
        from affinity.cli.interaction_utils import async_check_unreplied

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied(mock_client, "company", 456)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-001")
    @pytest.mark.asyncio
    async def test_accepts_opportunity_entity_type(self) -> None:
        """Accepts 'opportunity' entity type string."""
        from affinity.cli.interaction_utils import async_check_unreplied

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied(mock_client, "opportunity", 789)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-001")
    @pytest.mark.asyncio
    async def test_accepts_v1_integer_person_type(self) -> None:
        """Accepts V1 integer entity type (0 = person)."""
        from affinity.cli.interaction_utils import async_check_unreplied

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied(mock_client, 0, 123)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-001")
    @pytest.mark.asyncio
    async def test_accepts_v1_integer_company_type(self) -> None:
        """Accepts V1 integer entity type (1 = company)."""
        from affinity.cli.interaction_utils import async_check_unreplied

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied(mock_client, 1, 456)
        assert result is None

    @pytest.mark.req("QUERY-UNREPLIED-001")
    @pytest.mark.asyncio
    async def test_accepts_organization_entity_type(self) -> None:
        """Accepts 'organization' entity type (V1/V2 variant of company)."""
        from affinity.cli.interaction_utils import async_check_unreplied

        async def mock_iter(*_args: Any, **_kwargs: Any) -> Any:
            return
            yield

        mock_client = MagicMock()
        mock_client.interactions = MagicMock()
        mock_client.interactions.iter = mock_iter

        result = await async_check_unreplied(mock_client, "organization", 456)
        assert result is None


class TestUnrepliedExpansionSchema:
    """Tests for unreplied expansion schema configuration."""

    @pytest.mark.req("QUERY-UNREPLIED-002")
    def test_unreplied_in_expansion_registry(self) -> None:
        """unreplied is defined in EXPANSION_REGISTRY."""
        from affinity.cli.query.schema import EXPANSION_REGISTRY

        assert "unreplied" in EXPANSION_REGISTRY

        expansion = EXPANSION_REGISTRY["unreplied"]
        assert expansion.name == "unreplied"
        assert "persons" in expansion.supported_entities
        assert "companies" in expansion.supported_entities
        assert "opportunities" in expansion.supported_entities

    @pytest.mark.req("QUERY-UNREPLIED-002")
    def test_unreplied_emails_not_in_expansion_registry(self) -> None:
        """unrepliedEmails is NOT in EXPANSION_REGISTRY (breaking change verified)."""
        from affinity.cli.query.schema import EXPANSION_REGISTRY

        assert "unrepliedEmails" not in EXPANSION_REGISTRY

    @pytest.mark.req("QUERY-UNREPLIED-002")
    def test_list_entries_supports_unreplied_expansion(self) -> None:
        """listEntries schema includes unreplied in supported_expansions."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        list_entries_schema = SCHEMA_REGISTRY["listEntries"]
        assert "unreplied" in list_entries_schema.supported_expansions

    @pytest.mark.req("QUERY-UNREPLIED-002")
    def test_unreplied_does_not_require_refetch(self) -> None:
        """unreplied expansion does not require entity refetch."""
        from affinity.cli.query.schema import EXPANSION_REGISTRY

        expansion = EXPANSION_REGISTRY["unreplied"]
        assert expansion.requires_refetch is False


class TestUnrepliedExpansionExecution:
    """Tests for unreplied expansion execution in query executor."""

    @pytest.mark.req("QUERY-UNREPLIED-003")
    @pytest.mark.asyncio
    async def test_expand_list_entries_handles_unreplied(self) -> None:
        """_expand_list_entries handles unreplied expansion."""
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
        expansion_def = EXPANSION_REGISTRY["unreplied"]
        step = PlanStep(
            step_id=1,
            operation="expand",
            description="expand unreplied",
        )

        # Mock the async_check_unreplied function
        with patch("affinity.cli.interaction_utils.async_check_unreplied") as mock_check:
            mock_check.return_value = {
                "date": "2026-01-15",
                "daysSince": 3,
                "type": "email",
                "subject": "Test Email",
            }

            executor = QueryExecutor.__new__(QueryExecutor)
            executor.client = MagicMock()
            executor.rate_limiter = AsyncMock()
            executor.rate_limiter.__aenter__ = AsyncMock()
            executor.rate_limiter.__aexit__ = AsyncMock()
            executor.progress = MagicMock()  # Mock progress reporter

            await executor._expand_list_entries(step, ctx, expansion_def)

        # Verify unreplied added to records
        assert ctx.records[0].get("unreplied") is not None
        assert ctx.records[1].get("unreplied") is not None


class TestQueryWithUnrepliedExpansion:
    """Integration tests for query with unreplied expansion."""

    @pytest.mark.req("QUERY-UNREPLIED-004")
    def test_query_model_accepts_unreplied_expand(self) -> None:
        """Query model accepts unreplied in expand field."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "expand": ["unreplied"],
            }
        )

        assert query.expand is not None
        assert "unreplied" in query.expand

    @pytest.mark.req("QUERY-UNREPLIED-004")
    def test_query_model_accepts_multiple_expansions(self) -> None:
        """Query model accepts multiple expansions including unreplied."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "expand": ["interactionDates", "unreplied"],
            }
        )

        assert query.expand is not None
        assert "interactionDates" in query.expand
        assert "unreplied" in query.expand
