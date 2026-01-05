"""Additional tests for CLI list commands to improve coverage."""

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


class TestListLs:
    """Tests for list ls command."""

    def test_ls_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic list ls should work."""
        respx_mock.get("https://api.affinity.co/v2/lists").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "name": "Sales Pipeline",
                            "type": 0,
                            "isPublic": False,
                            "ownerId": 100,
                            "creatorId": 100,
                        },
                    ],
                    "pagination": {"nextUrl": None},
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "ls"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_with_type_filter(self, respx_mock: respx.MockRouter) -> None:
        """List ls with type parameter."""
        respx_mock.get("https://api.affinity.co/v2/lists").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "name": "Sales Pipeline",
                            "type": 0,
                            "isPublic": False,
                            "ownerId": 100,
                            "creatorId": 100,
                        },
                    ],
                    "pagination": {"nextUrl": None},
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "ls", "--type", "person"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_with_max_results(self, respx_mock: respx.MockRouter) -> None:
        """List ls with --max-results should limit output."""
        respx_mock.get("https://api.affinity.co/v2/lists").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "name": "List 1",
                            "type": 0,
                            "isPublic": False,
                            "ownerId": 100,
                            "creatorId": 100,
                        },
                        {
                            "id": 2,
                            "name": "List 2",
                            "type": 0,
                            "isPublic": False,
                            "ownerId": 100,
                            "creatorId": 100,
                        },
                        {
                            "id": 3,
                            "name": "List 3",
                            "type": 0,
                            "isPublic": False,
                            "ownerId": 100,
                            "creatorId": 100,
                        },
                    ],
                    "pagination": {"nextUrl": "https://api.affinity.co/v2/lists?cursor=next"},
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "ls", "--max-results", "2"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_ls_with_all_pages(self, respx_mock: respx.MockRouter) -> None:
        """List ls with --all flag."""
        respx_mock.get("https://api.affinity.co/v2/lists").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": 1,
                                "name": "List 1",
                                "type": 0,
                                "isPublic": False,
                                "ownerId": 100,
                                "creatorId": 100,
                            },
                        ],
                        "pagination": {"nextUrl": "https://api.affinity.co/v2/lists?cursor=page2"},
                    },
                ),
                Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": 2,
                                "name": "List 2",
                                "type": 0,
                                "isPublic": False,
                                "ownerId": 100,
                                "creatorId": 100,
                            },
                        ],
                        "pagination": {"nextUrl": None},
                    },
                ),
            ]
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "ls", "--all"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestListCreate:
    """Tests for list create command."""

    def test_create_basic(self, respx_mock: respx.MockRouter) -> None:
        """Basic list create should work."""
        respx_mock.post("https://api.affinity.co/lists").mock(
            return_value=Response(
                200,
                json={
                    "id": 123,
                    "name": "New List",
                    "type": 0,
                    "public": False,
                    "owner_id": 100,
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "create", "--name", "New List", "--type", "person"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_create_public(self, respx_mock: respx.MockRouter) -> None:
        """List create with --public flag."""
        respx_mock.post("https://api.affinity.co/lists").mock(
            return_value=Response(
                200,
                json={
                    "id": 123,
                    "name": "Public List",
                    "type": 1,
                    "public": True,
                    "owner_id": 100,
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "create", "--name", "Public List", "--type", "company", "--public"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestListGet:
    """Tests for list get command."""

    def test_get_by_id(self, respx_mock: respx.MockRouter) -> None:
        """Get list by numeric ID."""
        # Mock V1 list get (for ID resolution)
        respx_mock.get("https://api.affinity.co/lists/123").mock(
            return_value=Response(
                200,
                json={"id": 123, "name": "Pipeline", "type": 0, "public": False, "owner_id": 100},
            )
        )
        # Mock list fields endpoint
        respx_mock.get("https://api.affinity.co/v2/lists/123/fields").mock(
            return_value=Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
            )
        )
        # Mock saved views endpoint
        respx_mock.get("https://api.affinity.co/v2/lists/123/saved-views").mock(
            return_value=Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "get", "123"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_get_by_name(self, respx_mock: respx.MockRouter) -> None:
        """Get list by name."""
        respx_mock.get("https://api.affinity.co/v2/lists").mock(
            return_value=Response(
                200,
                json={
                    "data": [
                        {
                            "id": 456,
                            "name": "Pipeline",
                            "type": 0,
                            "isPublic": False,
                            "ownerId": 100,
                            "creatorId": 100,
                        },
                    ],
                    "pagination": {"nextUrl": None},
                },
            )
        )
        respx_mock.get("https://api.affinity.co/v2/lists/456/fields").mock(
            return_value=Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
            )
        )
        respx_mock.get("https://api.affinity.co/v2/lists/456/saved-views").mock(
            return_value=Response(
                200,
                json={"data": [], "pagination": {"nextUrl": None}},
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "get", "Pipeline"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestListEntryGet:
    """Tests for list entry get command."""

    def test_entry_get_basic(self, respx_mock: respx.MockRouter) -> None:
        """Get list entry by ID."""
        # Mock V1 list get (for ID resolution)
        respx_mock.get("https://api.affinity.co/lists/100").mock(
            return_value=Response(
                200,
                json={"id": 100, "name": "Pipeline", "type": 0, "public": False, "owner_id": 100},
            )
        )
        # Mock entry get (V2 endpoint - default routing)
        respx_mock.get("https://api.affinity.co/v2/lists/100/list-entries/999").mock(
            return_value=Response(
                200,
                json={
                    "id": 999,
                    "listId": 100,
                    "type": "person",
                    "createdAt": "2024-01-15T10:00:00Z",
                    "entity": {"id": 500, "firstName": "Test", "lastName": "Person"},
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "get", "100", "999"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestListEntryAdd:
    """Tests for list entry add command."""

    def test_entry_add_no_entity_fails(self) -> None:
        """Adding with no entity should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "add", "123"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2

    def test_entry_add_with_person_id(self, respx_mock: respx.MockRouter) -> None:
        """Add list entry with person ID."""
        # Mock V1 list get (for ID resolution)
        respx_mock.get("https://api.affinity.co/lists/100").mock(
            return_value=Response(
                200,
                json={"id": 100, "name": "Pipeline", "type": 0, "public": False, "owner_id": 100},
            )
        )
        # Mock add entry (V1 endpoint)
        respx_mock.post("https://api.affinity.co/lists/100/list-entries").mock(
            return_value=Response(
                200,
                json={
                    "id": 1001,
                    "list_id": 100,
                    "entity_id": 500,
                    "entity_type": 0,
                    "creator_id": 1,
                    "created_at": "2024-01-15T10:00:00Z",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "add", "100", "--person-id", "500"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_entry_add_with_company_id(self, respx_mock: respx.MockRouter) -> None:
        """Add list entry with company ID."""
        # Mock V1 list get (for ID resolution)
        respx_mock.get("https://api.affinity.co/lists/200").mock(
            return_value=Response(
                200,
                json={"id": 200, "name": "Companies", "type": 1, "public": False, "owner_id": 100},
            )
        )
        # Mock add entry (V1 endpoint)
        respx_mock.post("https://api.affinity.co/lists/200/list-entries").mock(
            return_value=Response(
                200,
                json={
                    "id": 2001,
                    "list_id": 200,
                    "entity_id": 600,
                    "entity_type": 1,
                    "creator_id": 1,
                    "created_at": "2024-01-15T10:00:00Z",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "add", "200", "--company-id", "600"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0

    def test_entry_add_both_ids_fails(self) -> None:
        """Adding with both person and company ID should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "add", "123", "--person-id", "1", "--company-id", "2"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2


class TestListEntryDelete:
    """Tests for list entry delete command."""

    def test_entry_delete_basic(self, respx_mock: respx.MockRouter) -> None:
        """Delete list entry by ID."""
        # Mock V1 list get (for ID resolution)
        respx_mock.get("https://api.affinity.co/lists/100").mock(
            return_value=Response(
                200,
                json={"id": 100, "name": "Pipeline", "type": 0, "public": False, "owner_id": 100},
            )
        )
        # Mock delete entry (V1 endpoint)
        respx_mock.delete("https://api.affinity.co/lists/100/list-entries/999").mock(
            return_value=Response(200, json={"success": True})
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "delete", "100", "999", "--yes"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        assert result.exit_code == 0


class TestListEntrySetField:
    """Tests for list entry set-field command."""

    def test_set_field_no_value_fails(self) -> None:
        """Setting field with no value should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "set-field", "123", "999", "--field", "Status"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2

    def test_set_field_both_values_fails(self) -> None:
        """Setting field with both --value and --value-json should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json",
                "list",
                "entry",
                "set-field",
                "123",
                "999",
                "--field",
                "Status",
                "--value",
                "Active",
                "--value-json",
                '"Active"',
            ],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2

    def test_set_field_no_field_specifier_fails(self) -> None:
        """Setting field with no --field or --field-id should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "set-field", "123", "999", "--value", "Active"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2


class TestListEntryUnsetField:
    """Tests for list entry unset-field command."""

    def test_unset_field_no_field_specifier_fails(self) -> None:
        """Unsetting field with no --field or --field-id should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "list", "entry", "unset-field", "123", "999"],
            env={"AFFINITY_API_KEY": "test-key"},
        )
        # Should fail with exit code 2 (usage error)
        assert result.exit_code == 2
