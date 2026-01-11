"""Tests for query schema registry."""

from __future__ import annotations

import pytest

from affinity.cli.query.schema import (
    SCHEMA_REGISTRY,
    EntitySchema,
    RelationshipDef,
    get_entity_relationships,
    get_entity_schema,
    get_relationship,
    get_supported_entities,
    is_valid_field_path,
)


class TestSchemaRegistry:
    """Tests for SCHEMA_REGISTRY."""

    @pytest.mark.req("QUERY-SCHEMA-001")
    def test_has_correct_fetch_strategies(self) -> None:
        """Schema registry has correct fetch strategies for relationships."""
        # Person -> companies uses entity_method
        persons = SCHEMA_REGISTRY["persons"]
        assert persons.relationships["companies"].fetch_strategy == "entity_method"
        assert persons.relationships["companies"].method_or_service == "get_associated_company_ids"

        # Person -> interactions uses global_service
        assert persons.relationships["interactions"].fetch_strategy == "global_service"
        assert persons.relationships["interactions"].method_or_service == "interactions"
        assert persons.relationships["interactions"].filter_field == "person_id"

    @pytest.mark.req("QUERY-SCHEMA-001")
    def test_all_entities_have_service_attr(self) -> None:
        """All entities have service_attr defined."""
        for name, schema in SCHEMA_REGISTRY.items():
            assert schema.service_attr is not None, f"Entity {name} missing service_attr"
            assert len(schema.service_attr) > 0

    @pytest.mark.req("QUERY-SCHEMA-001")
    def test_all_entities_have_id_field(self) -> None:
        """All entities have id_field defined."""
        for name, schema in SCHEMA_REGISTRY.items():
            assert schema.id_field is not None, f"Entity {name} missing id_field"
            assert schema.id_field == "id"  # Standard id field

    def test_supported_entities(self) -> None:
        """All expected entities are in registry."""
        expected = {"persons", "companies", "opportunities", "listEntries", "interactions", "notes"}
        actual = set(SCHEMA_REGISTRY.keys())
        assert expected == actual


class TestEntityMethodsExist:
    """Tests that verify SDK methods exist for entity_method fetch strategy."""

    @pytest.mark.req("QUERY-SCHEMA-002")
    def test_person_service_association_methods(self) -> None:
        """PersonService has required association methods."""
        from affinity.services.persons import PersonService  # noqa: PLC0415

        # Check sync methods exist
        assert hasattr(PersonService, "get_associated_company_ids")
        assert hasattr(PersonService, "get_associated_opportunity_ids")
        assert callable(PersonService.get_associated_company_ids)
        assert callable(PersonService.get_associated_opportunity_ids)

    @pytest.mark.req("QUERY-SCHEMA-002")
    def test_company_service_association_methods(self) -> None:
        """CompanyService has required association methods."""
        from affinity.services.companies import CompanyService  # noqa: PLC0415

        # Check sync methods exist
        assert hasattr(CompanyService, "get_associated_person_ids")
        assert hasattr(CompanyService, "get_associated_opportunity_ids")
        assert callable(CompanyService.get_associated_person_ids)
        assert callable(CompanyService.get_associated_opportunity_ids)

    @pytest.mark.req("QUERY-SCHEMA-002")
    def test_opportunity_service_association_methods(self) -> None:
        """OpportunityService has required association methods."""
        from affinity.services.opportunities import OpportunityService  # noqa: PLC0415

        # Check sync methods exist
        assert hasattr(OpportunityService, "get_associated_person_ids")
        assert hasattr(OpportunityService, "get_associated_company_ids")
        assert callable(OpportunityService.get_associated_person_ids)
        assert callable(OpportunityService.get_associated_company_ids)


class TestGlobalServicesExist:
    """Tests that verify global services exist for global_service fetch strategy."""

    @pytest.mark.req("QUERY-SCHEMA-003")
    def test_interaction_service_exists(self) -> None:
        """InteractionService exists and has list method."""
        from affinity.services.v1_only import InteractionService  # noqa: PLC0415

        assert hasattr(InteractionService, "list")
        assert callable(InteractionService.list)

    @pytest.mark.req("QUERY-SCHEMA-003")
    def test_note_service_exists(self) -> None:
        """NoteService exists and has list method."""
        from affinity.services.v1_only import NoteService  # noqa: PLC0415

        assert hasattr(NoteService, "list")
        assert callable(NoteService.list)


class TestGetEntitySchema:
    """Tests for get_entity_schema function."""

    def test_get_existing_entity(self) -> None:
        """Returns schema for existing entity."""
        schema = get_entity_schema("persons")
        assert schema is not None
        assert schema.name == "persons"
        assert schema.service_attr == "persons"

    def test_get_nonexistent_entity(self) -> None:
        """Returns None for nonexistent entity."""
        schema = get_entity_schema("nonexistent")
        assert schema is None


class TestGetRelationship:
    """Tests for get_relationship function."""

    def test_get_existing_relationship(self) -> None:
        """Returns relationship for existing relationship."""
        rel = get_relationship("persons", "companies")
        assert rel is not None
        assert rel.target_entity == "companies"
        assert rel.fetch_strategy == "entity_method"

    def test_get_nonexistent_relationship(self) -> None:
        """Returns None for nonexistent relationship."""
        rel = get_relationship("persons", "nonexistent")
        assert rel is None

    def test_get_relationship_nonexistent_entity(self) -> None:
        """Returns None for nonexistent entity."""
        rel = get_relationship("nonexistent", "companies")
        assert rel is None


class TestIsValidFieldPath:
    """Tests for is_valid_field_path function."""

    def test_simple_filterable_field(self) -> None:
        """Simple filterable field is valid."""
        assert is_valid_field_path("persons", "firstName") is True
        assert is_valid_field_path("persons", "lastName") is True
        assert is_valid_field_path("companies", "name") is True
        assert is_valid_field_path("companies", "domain") is True

    def test_id_field(self) -> None:
        """ID field is valid."""
        assert is_valid_field_path("persons", "id") is True
        assert is_valid_field_path("companies", "id") is True

    def test_computed_field(self) -> None:
        """Computed fields are valid."""
        assert is_valid_field_path("persons", "firstEmail") is True
        assert is_valid_field_path("persons", "lastEmail") is True

    def test_relationship_count(self) -> None:
        """Relationship _count is valid."""
        assert is_valid_field_path("persons", "companies._count") is True
        assert is_valid_field_path("companies", "people._count") is True

    def test_fields_prefix(self) -> None:
        """fields.* is always valid (for list entries)."""
        assert is_valid_field_path("listEntries", "fields.Status") is True
        assert is_valid_field_path("listEntries", "fields.Custom Field") is True
        assert is_valid_field_path("persons", "fields.anything") is True

    def test_invalid_field(self) -> None:
        """Invalid field is not valid."""
        assert is_valid_field_path("persons", "nonexistent") is False
        assert is_valid_field_path("companies", "unknownField") is False

    def test_nonexistent_entity(self) -> None:
        """Nonexistent entity returns False."""
        assert is_valid_field_path("nonexistent", "name") is False


class TestGetSupportedEntities:
    """Tests for get_supported_entities function."""

    def test_returns_all_entities(self) -> None:
        """Returns all supported entity types."""
        entities = get_supported_entities()
        assert "persons" in entities
        assert "companies" in entities
        assert "opportunities" in entities
        assert "listEntries" in entities
        assert "interactions" in entities
        assert "notes" in entities
        assert len(entities) == 6


class TestGetEntityRelationships:
    """Tests for get_entity_relationships function."""

    def test_person_relationships(self) -> None:
        """Returns all relationships for persons."""
        rels = get_entity_relationships("persons")
        assert "companies" in rels
        assert "opportunities" in rels
        assert "interactions" in rels
        assert "notes" in rels
        assert "listEntries" in rels

    def test_company_relationships(self) -> None:
        """Returns all relationships for companies."""
        rels = get_entity_relationships("companies")
        assert "people" in rels
        assert "opportunities" in rels
        assert "interactions" in rels
        assert "notes" in rels

    def test_nonexistent_entity(self) -> None:
        """Returns empty list for nonexistent entity."""
        rels = get_entity_relationships("nonexistent")
        assert rels == []


class TestRelationshipDef:
    """Tests for RelationshipDef dataclass."""

    def test_default_values(self) -> None:
        """RelationshipDef has correct defaults."""
        rel = RelationshipDef(
            target_entity="companies",
            fetch_strategy="entity_method",
            method_or_service="get_companies",
        )
        assert rel.filter_field is None
        assert rel.cardinality == "many"
        assert rel.requires_n_plus_1 is True

    def test_frozen(self) -> None:
        """RelationshipDef is frozen (immutable)."""
        rel = RelationshipDef(
            target_entity="companies",
            fetch_strategy="entity_method",
            method_or_service="get_companies",
        )
        with pytest.raises(AttributeError):
            rel.target_entity = "other"  # type: ignore


class TestEntitySchema:
    """Tests for EntitySchema dataclass."""

    def test_default_api_version(self) -> None:
        """EntitySchema defaults to v2 API."""
        schema = EntitySchema(
            name="test",
            service_attr="test",
            id_field="id",
            filterable_fields=frozenset(),
            computed_fields=frozenset(),
            relationships={},
        )
        assert schema.api_version == "v2"

    def test_frozen(self) -> None:
        """EntitySchema is frozen (immutable)."""
        schema = EntitySchema(
            name="test",
            service_attr="test",
            id_field="id",
            filterable_fields=frozenset(),
            computed_fields=frozenset(),
            relationships={},
        )
        with pytest.raises(AttributeError):
            schema.name = "other"  # type: ignore
