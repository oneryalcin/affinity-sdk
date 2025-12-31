"""Unit tests for CommandContext.format_header() patterns."""

from __future__ import annotations

from affinity.cli.results import CommandContext


class TestFormatHeaderGetCommands:
    """Tests for entity get command headers."""

    def test_person_get_with_resolved(self) -> None:
        ctx = CommandContext(
            name="person get",
            inputs={"personId": 12345},
            modifiers={},
            resolved={"personId": "John Doe"},
        )
        assert ctx.format_header() == 'Person "John Doe" (ID 12345)'

    def test_person_get_without_resolved(self) -> None:
        ctx = CommandContext(
            name="person get",
            inputs={"personId": 12345},
            modifiers={},
        )
        assert ctx.format_header() == "Person ID 12345"

    def test_company_get_with_selector(self) -> None:
        ctx = CommandContext(
            name="company get",
            inputs={"selector": "domain:acme.com"},
            modifiers={},
            resolved={"selector": "Acme Inc"},
        )
        assert ctx.format_header() == 'Company "Acme Inc" (domain:acme.com)'

    def test_company_get_selector_without_resolved(self) -> None:
        ctx = CommandContext(
            name="company get",
            inputs={"selector": "domain:acme.com"},
            modifiers={},
        )
        assert ctx.format_header() == "Company domain:acme.com"

    def test_opportunity_get(self) -> None:
        ctx = CommandContext(
            name="opportunity get",
            inputs={"opportunityId": 999},
            modifiers={},
        )
        assert ctx.format_header() == "Opportunity ID 999"


class TestFormatHeaderLsCommands:
    """Tests for list command headers."""

    def test_person_ls_no_filters(self) -> None:
        ctx = CommandContext(
            name="person ls",
            inputs={},
            modifiers={},
        )
        assert ctx.format_header() == "Persons"

    def test_note_ls_with_person_filter(self) -> None:
        ctx = CommandContext(
            name="note ls",
            inputs={},
            modifiers={"personId": 123},
        )
        assert ctx.format_header() == "Notes for Person ID 123"

    def test_reminder_ls_multiple_filters(self) -> None:
        ctx = CommandContext(
            name="reminder ls",
            inputs={},
            modifiers={"status": "active", "type": "recurring"},
        )
        assert ctx.format_header() == "Reminders (status: active, type: recurring)"

    def test_field_value_ls_truncation(self) -> None:
        ctx = CommandContext(
            name="field-value ls",
            inputs={},
            modifiers={"personId": 1, "companyId": 2, "opportunityId": 3},
        )
        # Multiple entity filters use parenthetical format with shortened keys
        assert ctx.format_header() == "Field Values (person: 1, company: 2, +1 more)"

    def test_relationship_strength_composite_keys(self) -> None:
        ctx = CommandContext(
            name="relationship-strength ls",
            inputs={"internalId": 123, "externalId": 456},
            modifiers={},
        )
        assert ctx.format_header() == "Relationship Strength: Person ID 123 ↔ Person ID 456"

    def test_list_entry_ls_with_list_id(self) -> None:
        ctx = CommandContext(
            name="list entry ls",
            inputs={"listId": 41780},
            modifiers={},
        )
        assert ctx.format_header() == "List Entrys: List ID 41780"

    def test_list_entry_ls_with_resolved(self) -> None:
        ctx = CommandContext(
            name="list entry ls",
            inputs={"listId": 41780},
            modifiers={},
            resolved={"listId": "Dealflow"},
        )
        assert ctx.format_header() == 'List Entrys: List "Dealflow"'

    def test_interaction_ls_with_type_filter(self) -> None:
        ctx = CommandContext(
            name="interaction ls",
            inputs={},
            modifiers={"type": "email"},
        )
        assert ctx.format_header() == "Interactions (type: email)"

    def test_notes_for_person_with_additional_filter(self) -> None:
        ctx = CommandContext(
            name="note ls",
            inputs={},
            modifiers={"personId": 123, "creatorId": 456},
        )
        assert ctx.format_header() == "Notes for Person ID 123 (creator: 456)"


class TestFormatHeaderCreateCommands:
    """Tests for create command headers."""

    def test_opportunity_create_with_list(self) -> None:
        ctx = CommandContext(
            name="opportunity create",
            inputs={"listId": 41780},
            modifiers={"name": "New Deal"},
            resolved={"listId": "Dealflow"},
        )
        assert ctx.format_header() == 'Opportunity Create: List "Dealflow"'

    def test_opportunity_create_without_resolved(self) -> None:
        ctx = CommandContext(
            name="opportunity create",
            inputs={"listId": 41780},
            modifiers={"name": "New Deal"},
        )
        assert ctx.format_header() == "Opportunity Create: List ID 41780"

    def test_interaction_create_with_type(self) -> None:
        ctx = CommandContext(
            name="interaction create",
            inputs={"type": "meeting"},
            modifiers={"personIds": [1, 2]},
        )
        assert ctx.format_header() == "Interaction Create (type: meeting)"

    def test_person_create(self) -> None:
        ctx = CommandContext(
            name="person create",
            inputs={},
            modifiers={"firstName": "John", "lastName": "Doe"},
        )
        assert ctx.format_header() == "Person Create"


class TestFormatHeaderMutationCommands:
    """Tests for update/delete command headers."""

    def test_person_update_with_resolved(self) -> None:
        ctx = CommandContext(
            name="person update",
            inputs={"personId": 12345},
            modifiers={"firstName": "Jane"},
            resolved={"personId": "John Doe"},
        )
        assert ctx.format_header() == 'Person Update: "John Doe" (ID 12345)'

    def test_person_update_without_resolved(self) -> None:
        ctx = CommandContext(
            name="person update",
            inputs={"personId": 12345},
            modifiers={"firstName": "Jane"},
        )
        assert ctx.format_header() == "Person Update: ID 12345"

    def test_note_delete(self) -> None:
        ctx = CommandContext(
            name="note delete",
            inputs={"noteId": 999},
            modifiers={},
        )
        assert ctx.format_header() == "Note Delete: ID 999"


class TestFormatHeaderMergeCommands:
    """Tests for merge command headers."""

    def test_person_merge(self) -> None:
        ctx = CommandContext(
            name="person merge",
            inputs={"primaryId": 100, "duplicateId": 200},
            modifiers={},
        )
        assert ctx.format_header() == "Person Merge: ID 100 ← ID 200"

    def test_company_merge(self) -> None:
        ctx = CommandContext(
            name="company merge",
            inputs={"primaryId": 10, "duplicateId": 20},
            modifiers={},
        )
        assert ctx.format_header() == "Company Merge: ID 10 ← ID 20"


class TestFormatHeaderSpecialCases:
    """Tests for special cases and edge conditions."""

    def test_whoami_returns_none(self) -> None:
        ctx = CommandContext(name="whoami", inputs={}, modifiers={})
        assert ctx.format_header() is None

    def test_single_word_command_returns_none(self) -> None:
        ctx = CommandContext(name="version", inputs={}, modifiers={})
        assert ctx.format_header() is None

    def test_config_command_returns_none(self) -> None:
        ctx = CommandContext(name="config", inputs={}, modifiers={})
        assert ctx.format_header() is None

    def test_unknown_entity_uses_title_case(self) -> None:
        ctx = CommandContext(
            name="custom-entity get",
            inputs={"customEntityId": 123},
            modifiers={},
        )
        # Unknown entity type gets title-cased
        assert ctx.format_header() == "Custom-Entity"

    def test_pagination_modifiers_excluded_from_display(self) -> None:
        ctx = CommandContext(
            name="person ls",
            inputs={},
            modifiers={"pageSize": 100, "cursor": "abc123", "maxResults": 500, "allPages": True},
        )
        # Pagination modifiers should not appear in header
        assert ctx.format_header() == "Persons"

    def test_none_modifier_values_excluded(self) -> None:
        ctx = CommandContext(
            name="note ls",
            inputs={},
            modifiers={"personId": 123, "companyId": None, "opportunityId": None},
        )
        assert ctx.format_header() == "Notes for Person ID 123"
