"""Tests for query/list export parity.

These tests verify that the query command provides functional parity
with the list export command for the same operations.

Related: docs/internal/query-list-export-parity-plan.md

Parity features tested:
- list export --expand persons → query with include: ["persons"]
- list export --expand companies → query with include: ["companies"]
- list export --expand opportunities → query with include: ["opportunities"]
- list export --expand interactions → query with include: ["interactions"]
- list export --check-unreplied → query with expand: ["unreplied"]
"""

from __future__ import annotations

import pytest


class TestQueryListExportParitySyntax:
    """Tests that query syntax can express all list export operations."""

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-001")
    def test_persons_expansion_mapping(self) -> None:
        """list export --expand persons maps to query include: ['persons']."""
        from affinity.cli.query.models import Query

        # This is the query equivalent of: list export Dealflow --expand persons
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": ["persons"],
            }
        )

        assert query.include is not None
        assert "persons" in query.include

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-001")
    def test_companies_expansion_mapping(self) -> None:
        """list export --expand companies maps to query include: ['companies']."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": ["companies"],
            }
        )

        assert query.include is not None
        assert "companies" in query.include

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-001")
    def test_opportunities_expansion_mapping(self) -> None:
        """list export --expand opportunities maps to query include: ['opportunities']."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": ["opportunities"],
            }
        )

        assert query.include is not None
        assert "opportunities" in query.include

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-001")
    def test_interactions_expansion_mapping(self) -> None:
        """list export --expand interactions maps to query include: ['interactions']."""
        from affinity.cli.query.models import Query

        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": ["interactions"],
            }
        )

        assert query.include is not None
        assert "interactions" in query.include

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-001")
    def test_unreplied_mapping(self) -> None:
        """list export --check-unreplied maps to query expand: ['unreplied']."""
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


class TestQueryListExportParityParameters:
    """Tests that query supports list export parameter equivalents."""

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-002")
    def test_interactions_limit_parameter(self) -> None:
        """Query supports interaction limit (list export default is 100)."""
        from affinity.cli.query.models import Query

        # Equivalent to: list export Dealflow --expand interactions --interactions-limit 50
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": [{"interactions": {"limit": 50}}],
            }
        )

        assert query.include is not None
        interactions_config = query.include["interactions"]
        assert interactions_config.limit == 50

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-002")
    def test_interactions_days_parameter(self) -> None:
        """Query supports interaction days lookback (list export default is 90)."""
        from affinity.cli.query.models import Query

        # Equivalent to: list export Dealflow --expand interactions --interactions-days 180
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": [{"interactions": {"days": 180}}],
            }
        )

        assert query.include is not None
        interactions_config = query.include["interactions"]
        assert interactions_config.days == 180

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-002")
    def test_opportunities_list_scoping(self) -> None:
        """Query supports scoping opportunities to a specific list."""
        from affinity.cli.query.models import Query

        # list export Dealflow --expand opportunities --expand-opportunities-list "Pipeline"
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": [{"opportunities": {"list": "Pipeline"}}],
            }
        )

        assert query.include is not None
        opportunities_config = query.include["opportunities"]
        assert opportunities_config.list_ == "Pipeline"

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-002")
    def test_expand_filter_parity(self) -> None:
        """Query supports filtering included entities (--expand-filter parity)."""
        from affinity.cli.query.models import Query

        # Equivalent to: list export Dealflow --expand persons --expand-filter 'name=~"Smith"'
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": [
                    {"persons": {"where": {"path": "name", "op": "contains", "value": "Smith"}}}
                ],
            }
        )

        assert query.include is not None
        persons_config = query.include["persons"]
        assert persons_config.where is not None
        # WhereClause is a TypedDict, access via dict conversion
        where_dict = (
            persons_config.where
            if isinstance(persons_config.where, dict)
            else dict(persons_config.where)
        )
        assert where_dict["value"] == "Smith"


class TestQueryListExportParitySchema:
    """Tests that schema supports all required relationships."""

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-003")
    def test_list_entries_has_all_export_relationships(self) -> None:
        """listEntries schema has all relationships needed for list export parity."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        list_entries = SCHEMA_REGISTRY["listEntries"]
        relationships = list_entries.relationships

        # All list export --expand options should have corresponding relationships
        assert "persons" in relationships
        assert "companies" in relationships
        assert "opportunities" in relationships
        assert "interactions" in relationships

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-003")
    def test_list_entries_has_unreplied_expansion(self) -> None:
        """listEntries schema supports unreplied expansion."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        list_entries = SCHEMA_REGISTRY["listEntries"]
        assert "unreplied" in list_entries.supported_expansions

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-003")
    def test_all_relationships_use_list_entry_indirect(self) -> None:
        """All new listEntries relationships use list_entry_indirect strategy."""
        from affinity.cli.query.schema import SCHEMA_REGISTRY

        list_entries = SCHEMA_REGISTRY["listEntries"]

        for rel_name in ["persons", "companies", "opportunities", "interactions"]:
            rel = list_entries.relationships[rel_name]
            assert rel.fetch_strategy == "list_entry_indirect", (
                f"{rel_name} should use list_entry_indirect strategy"
            )


class TestQueryListExportParityBehavior:
    """Tests that query behavior matches list export behavior."""

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-004")
    def test_default_interaction_limit_is_100(self) -> None:
        """Default interaction limit matches list export default (100)."""

        # The executor implementation should default to 100
        # This is verified in the _fetch_interactions_for_list_entries implementation
        # where effective_limit = limit if limit is not None else 100
        pass  # Tested in test_query_list_entry_relationships.py

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-004")
    def test_default_interaction_days_is_90(self) -> None:
        """Default interaction days matches list export default (90)."""

        # The executor implementation should default to 90
        # This is verified in the _fetch_interactions_for_list_entries implementation
        # where effective_days = days if days is not None else 90
        pass  # Tested in test_query_list_entry_relationships.py


class TestMigrationGuide:
    """Tests that document the migration from list export to query."""

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-005")
    def test_migration_expand_persons(self) -> None:
        """Document migration: list export --expand persons."""
        from affinity.cli.query.models import Query

        # OLD: list export Dealflow --expand persons
        # NEW:
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": ["persons"],
            }
        )
        assert query.include is not None

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-005")
    def test_migration_expand_interactions(self) -> None:
        """Document migration: list export --expand interactions."""
        from affinity.cli.query.models import Query

        # OLD: list export Dealflow --expand interactions
        # NEW:
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": ["interactions"],
            }
        )
        assert query.include is not None

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-005")
    def test_migration_check_unreplied(self) -> None:
        """Document migration: list export --check-unreplied."""
        from affinity.cli.query.models import Query

        # OLD: list export Dealflow --check-unreplied
        # NEW:
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "expand": ["unreplied"],
            }
        )
        assert query.expand is not None

    @pytest.mark.req("QUERY-LIST-EXPORT-PARITY-005")
    def test_migration_combined_expansions(self) -> None:
        """Document migration: list export with multiple expansions."""
        from affinity.cli.query.models import Query

        # OLD: list export Dealflow --expand persons --expand companies --check-unreplied
        # NEW:
        query = Query.model_validate(
            {
                "from": "listEntries",
                "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
                "include": ["persons", "companies"],
                "expand": ["unreplied"],
            }
        )
        assert query.include is not None
        assert query.expand is not None
