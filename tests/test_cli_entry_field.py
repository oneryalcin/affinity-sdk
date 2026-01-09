"""Tests for the unified 'entry field' command.

Tests cover:
- --set, --append, --unset, --unset-value, --set-json, --get operations
- Operation exclusivity and conflict validations
- Field ID auto-detection
- JSON output format
- Error handling
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

try:
    import respx
except ModuleNotFoundError:  # pragma: no cover - optional dev dependency
    respx = None  # type: ignore[assignment]

from click.testing import CliRunner
from httpx import Response

from affinity.cli.main import cli

if respx is None:  # pragma: no cover
    pytest.skip("respx is not installed", allow_module_level=True)


# Common test fixtures
LIST_ID = 67890
ENTRY_ID = 123

LIST_RESPONSE = {
    "id": LIST_ID,
    "name": "Portfolio",
    "type": 0,  # Regular list
    "isPublic": False,
    "ownerId": 100,
    "creatorId": 100,
}

FIELDS_RESPONSE = [
    {"id": "field-100", "name": "Status", "valueType": 0, "allowsMultiple": False},
    {"id": "field-101", "name": "Priority", "valueType": 0, "allowsMultiple": False},
    {"id": "field-102", "name": "Tags", "valueType": 0, "allowsMultiple": True},
]

FIELD_VALUE_RESPONSE = {
    "id": 999,
    "fieldId": "field-100",
    "entityId": 224925,  # Some entity ID
    "value": "Active",
    "listEntryId": ENTRY_ID,
}


def setup_list_mocks(respx_mock: respx.MockRouter) -> None:
    """Set up common list resolution and field metadata mocks."""
    # List resolution by name (V2 API)
    respx_mock.get("https://api.affinity.co/v2/lists").mock(
        return_value=Response(200, json={"data": [LIST_RESPONSE], "pagination": {}})
    )
    # Field metadata
    respx_mock.get(f"https://api.affinity.co/v2/lists/{LIST_ID}/fields").mock(
        return_value=Response(200, json={"data": FIELDS_RESPONSE, "pagination": {}})
    )


# ============================================================================
# Basic Operation Tests
# ============================================================================


def test_entry_field_set_single(respx_mock: respx.MockRouter) -> None:
    """--set replaces existing field value."""
    setup_list_mocks(respx_mock)

    # No existing values
    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))
    # V2 API update
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(return_value=Response(200, json=FIELD_VALUE_RESPONSE))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", str(ENTRY_ID), "--set", "Status", "Active"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert "created" in payload["data"]
    assert len(payload["data"]["created"]) == 1


def test_entry_field_set_multiple(respx_mock: respx.MockRouter) -> None:
    """Multiple --set options work."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(return_value=Response(200, json=FIELD_VALUE_RESPONSE))
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-101"
    ).mock(
        return_value=Response(
            200, json={"id": 1000, "fieldId": "field-101", "entityId": 224925, "value": "High"}
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "Status",
            "Active",
            "--set",
            "Priority",
            "High",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert len(payload["data"]["created"]) == 2


def test_entry_field_append(respx_mock: respx.MockRouter) -> None:
    """--append adds to multi-value field."""
    setup_list_mocks(respx_mock)

    # Existing tag value
    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-102", "entityId": 224925, "value": "Existing"}],
        )
    )
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-102"
    ).mock(
        return_value=Response(
            200, json={"id": 501, "fieldId": "field-102", "entityId": 224925, "value": "NewTag"}
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--append",
            "Tags",
            "NewTag",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert "created" in payload["data"]
    # Append doesn't delete existing, so no deleted count
    assert "deleted" not in payload["data"]


def test_entry_field_unset(respx_mock: respx.MockRouter) -> None:
    """--unset removes all values for field."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-100", "entityId": 224925, "value": "Active"}],
        )
    )
    respx_mock.delete("https://api.affinity.co/field-values/500").mock(
        return_value=Response(200, json={"success": True})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", str(ENTRY_ID), "--unset", "Status"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["deleted"] == 1


def test_entry_field_unset_value(respx_mock: respx.MockRouter) -> None:
    """--unset-value removes specific value."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[
                {"id": 500, "fieldId": "field-102", "entityId": 224925, "value": "Tag1"},
                {"id": 501, "fieldId": "field-102", "entityId": 224925, "value": "Tag2"},
            ],
        )
    )
    respx_mock.delete("https://api.affinity.co/field-values/500").mock(
        return_value=Response(200, json={"success": True})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--unset-value",
            "Tags",
            "Tag1",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["deleted"] == 1


def test_entry_field_set_json(respx_mock: respx.MockRouter) -> None:
    """--set-json batch updates fields."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(return_value=Response(200, json=FIELD_VALUE_RESPONSE))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set-json",
            '{"Status": "Active"}',
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert len(payload["data"]["created"]) == 1


def test_entry_field_get(respx_mock: respx.MockRouter) -> None:
    """--get retrieves field values."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-100", "entityId": 224925, "value": "Active"}],
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", str(ENTRY_ID), "--get", "Status"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload["data"]["fields"]["Status"] == "Active"


def test_entry_field_get_output_format(respx_mock: respx.MockRouter) -> None:
    """--get returns {fields: {name: value}} format."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-100", "entityId": 224925, "value": "Active"}],
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", str(ENTRY_ID), "--get", "Status"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert "fields" in payload["data"]
    assert "Status" in payload["data"]["fields"]


def test_entry_field_get_resolves_field_names(respx_mock: respx.MockRouter) -> None:
    """--get with field ID outputs resolved field name as key."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-100", "entityId": 224925, "value": "Active"}],
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", str(ENTRY_ID), "--get", "field-100"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    # Field name should be resolved
    assert "Status" in payload["data"]["fields"]


# ============================================================================
# Validation Tests
# ============================================================================


def test_entry_field_no_operation_error() -> None:
    """Must specify at least one operation."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["entry", "field", "Portfolio", "123"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "No operation specified" in result.output


def test_entry_field_get_exclusive_with_set(respx_mock: respx.MockRouter) -> None:
    """--get cannot be combined with --set."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--get",
            "Status",
            "--set",
            "Status",
            "Active",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "--get cannot be combined" in result.output


def test_entry_field_get_exclusive_with_append(respx_mock: respx.MockRouter) -> None:
    """--get cannot be combined with --append."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--get",
            "Status",
            "--append",
            "Tags",
            "NewTag",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "--get cannot be combined" in result.output


def test_entry_field_get_exclusive_with_unset(respx_mock: respx.MockRouter) -> None:
    """--get cannot be combined with --unset."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["entry", "field", "Portfolio", "123", "--get", "Status", "--unset", "Status"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "--get cannot be combined" in result.output


def test_entry_field_get_exclusive_with_unset_value(
    respx_mock: respx.MockRouter,
) -> None:
    """--get cannot be combined with --unset-value."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--get",
            "Status",
            "--unset-value",
            "Tags",
            "Tag1",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "--get cannot be combined" in result.output


def test_entry_field_get_exclusive_with_set_json(respx_mock: respx.MockRouter) -> None:
    """--get cannot be combined with --set-json."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--get",
            "Status",
            "--set-json",
            '{"Status": "Active"}',
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "--get cannot be combined" in result.output


def test_entry_field_same_field_set_append_conflict(
    respx_mock: respx.MockRouter,
) -> None:
    """Same field in --set and --append raises error."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--set",
            "Tags",
            "New",
            "--append",
            "Tags",
            "Another",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field(s) in both --set and --append" in result.output


def test_entry_field_same_field_set_unset_conflict(
    respx_mock: respx.MockRouter,
) -> None:
    """Same field in --set and --unset raises error."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--set",
            "Status",
            "Active",
            "--unset",
            "Status",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field(s) in both --set and --unset" in result.output


def test_entry_field_same_field_append_unset_conflict(
    respx_mock: respx.MockRouter,
) -> None:
    """Same field in --append and --unset raises error."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--append",
            "Tags",
            "New",
            "--unset",
            "Tags",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field(s) in both --append and --unset" in result.output


def test_entry_field_same_field_set_unset_value_conflict(
    respx_mock: respx.MockRouter,
) -> None:
    """Same field in --set and --unset-value raises error."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--set",
            "Tags",
            "New",
            "--unset-value",
            "Tags",
            "Old",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field(s) in both --set and --unset-value" in result.output


def test_entry_field_same_field_unset_unset_value_conflict(
    respx_mock: respx.MockRouter,
) -> None:
    """Same field in --unset and --unset-value raises error (redundant)."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--unset",
            "Tags",
            "--unset-value",
            "Tags",
            "Old",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field(s) in both --unset and --unset-value" in result.output


def test_entry_field_append_unset_value_same_field_allowed(
    respx_mock: respx.MockRouter,
) -> None:
    """Same field in --append and --unset-value is allowed (tag swap pattern)."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-102", "entityId": 224925, "value": "OldTag"}],
        )
    )
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-102"
    ).mock(
        return_value=Response(
            200, json={"id": 501, "fieldId": "field-102", "entityId": 224925, "value": "NewTag"}
        )
    )
    respx_mock.delete("https://api.affinity.co/field-values/500").mock(
        return_value=Response(200, json={"success": True})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--append",
            "Tags",
            "NewTag",
            "--unset-value",
            "Tags",
            "OldTag",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert len(payload["data"]["created"]) == 1
    assert payload["data"]["deleted"] == 1


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_entry_field_malformed_set_json(respx_mock: respx.MockRouter) -> None:
    """Malformed --set-json gives clear error message."""
    setup_list_mocks(respx_mock)
    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--set-json",
            "{invalid json}",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Invalid JSON" in result.output


def test_entry_field_set_json_non_object(respx_mock: respx.MockRouter) -> None:
    """--set-json with array or primitive raises error (must be object)."""
    setup_list_mocks(respx_mock)
    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            "123",
            "--set-json",
            '["Status", "Active"]',
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "must be a JSON object" in result.output


def test_entry_field_empty_set_json(respx_mock: respx.MockRouter) -> None:
    """Empty --set-json '{}' is valid but no-op."""
    setup_list_mocks(respx_mock)
    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", "123", "--set-json", "{}"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    # No created or deleted since empty
    assert "created" not in payload["data"]
    assert "deleted" not in payload["data"]


def test_entry_field_unset_value_idempotent(respx_mock: respx.MockRouter) -> None:
    """--unset-value with nonexistent value succeeds silently."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            "123",
            "--unset-value",
            "Tags",
            "NonexistentTag",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    # Should succeed but with warning (visible in stderr)


# ============================================================================
# Field ID Auto-Detection Tests
# ============================================================================


def test_entry_field_id_auto_detection(respx_mock: respx.MockRouter) -> None:
    """Field IDs (field-123) detected and used directly."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(return_value=Response(200, json=FIELD_VALUE_RESPONSE))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "field-100",
            "Active",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output


def test_entry_field_enriched_id_auto_detection(respx_mock: respx.MockRouter) -> None:
    """Enriched field IDs (affinity-data-*) detected and used directly."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/affinity-data-location"
    ).mock(
        return_value=Response(
            200,
            json={
                "id": 999,
                "fieldId": "affinity-data-location",
                "entityId": 224925,
                "value": "NYC",
            },
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "affinity-data-location",
            "NYC",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output


# ============================================================================
# JSON Output Format Tests
# ============================================================================


def test_entry_field_json_output_format(respx_mock: respx.MockRouter) -> None:
    """JSON output includes command context and created/deleted counts."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-100", "entityId": 224925, "value": "Old"}],
        )
    )
    respx_mock.delete("https://api.affinity.co/field-values/500").mock(
        return_value=Response(200, json={"success": True})
    )
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(return_value=Response(200, json=FIELD_VALUE_RESPONSE))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "Status",
            "Active",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())

    # Check structure
    assert "data" in payload
    assert "command" in payload
    assert payload["command"]["name"] == "entry field"
    assert payload["command"]["inputs"]["entryId"] == ENTRY_ID
    assert "created" in payload["data"]
    assert "deleted" in payload["data"]


def test_entry_field_mixed_operations(respx_mock: respx.MockRouter) -> None:
    """--set and --unset can be combined on different fields."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-101", "entityId": 224925, "value": "Low"}],
        )
    )
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(return_value=Response(200, json=FIELD_VALUE_RESPONSE))
    respx_mock.delete("https://api.affinity.co/field-values/500").mock(
        return_value=Response(200, json={"success": True})
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "Status",
            "Active",
            "--unset",
            "Priority",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert len(payload["data"]["created"]) == 1
    assert payload["data"]["deleted"] == 1


def test_entry_field_multivalue_set_replaces(respx_mock: respx.MockRouter) -> None:
    """--set on multi-value field replaces all values (with warning)."""
    setup_list_mocks(respx_mock)

    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[
                {"id": 500, "fieldId": "field-102", "entityId": 224925, "value": "Tag1"},
                {"id": 501, "fieldId": "field-102", "entityId": 224925, "value": "Tag2"},
            ],
        )
    )
    respx_mock.delete("https://api.affinity.co/field-values/500").mock(
        return_value=Response(200, json={"success": True})
    )
    respx_mock.delete("https://api.affinity.co/field-values/501").mock(
        return_value=Response(200, json={"success": True})
    )
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-102"
    ).mock(
        return_value=Response(
            200, json={"id": 502, "fieldId": "field-102", "entityId": 224925, "value": "NewOnly"}
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "Tags",
            "NewOnly",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    # Check warning was printed (goes to output in test environment)
    assert "Warning: Replaced 2 existing values" in result.output
    # Extract JSON from output (skip warning line)
    json_line = next(line for line in result.output.split("\n") if line.startswith("{"))
    payload = json.loads(json_line)
    assert payload["data"]["deleted"] == 2


def test_entry_field_duplicate_field_in_set_operations(
    respx_mock: respx.MockRouter,
) -> None:
    """Same field in --set and --set-json raises error."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "Status",
            "Active",
            "--set-json",
            '{"Status": "Inactive"}',
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field(s) in both --set and --set-json" in result.output


# ============================================================================
# Operation Order and Field Resolution Tests
# ============================================================================


def test_entry_field_numeric_field_name(respx_mock: respx.MockRouter) -> None:
    """Numeric-only field name (e.g., '2024') treated as name, not ID."""
    # Add a field named "2024" to the field metadata
    fields_with_numeric = [
        *FIELDS_RESPONSE,
        {"id": "field-200", "name": "2024", "valueType": 0, "allowsMultiple": False},
    ]
    respx_mock.get("https://api.affinity.co/v2/lists").mock(
        return_value=Response(200, json={"data": [LIST_RESPONSE], "pagination": {}})
    )
    respx_mock.get(f"https://api.affinity.co/v2/lists/{LIST_ID}/fields").mock(
        return_value=Response(200, json={"data": fields_with_numeric, "pagination": {}})
    )
    respx_mock.get("https://api.affinity.co/field-values").mock(return_value=Response(200, json=[]))
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-200"
    ).mock(
        return_value=Response(
            200, json={"id": 999, "fieldId": "field-200", "entityId": 224925, "value": "Completed"}
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", str(ENTRY_ID), "--set", "2024", "Completed"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    # Verify the field was created - the command resolved "2024" as a name, not an ID
    created = payload["data"]["created"][0]
    # The created object wraps the API response in a "data" key
    field_data = created.get("data", created)
    assert field_data.get("fieldId") == "field-200"


def test_entry_field_field_not_found(respx_mock: respx.MockRouter) -> None:
    """Field ID not on list returns error."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["entry", "field", "Portfolio", str(ENTRY_ID), "--get", "field-99999"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field 'field-99999' not found on list" in result.output


def test_entry_field_field_name_not_found(respx_mock: respx.MockRouter) -> None:
    """Field name not on list returns error."""
    setup_list_mocks(respx_mock)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["entry", "field", "Portfolio", str(ENTRY_ID), "--get", "NonExistentField"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "NonExistentField" in result.output


def test_entry_field_resolution_upfront(respx_mock: respx.MockRouter) -> None:
    """All field names resolved before any API calls (fail-fast).

    If one field in a batch is invalid, the command should error before any
    API calls are made (no partial updates).
    """
    setup_list_mocks(respx_mock)
    # Note: no field_values mock - if we get that far, the test should fail

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "Status",
            "Active",
            "--set",
            "InvalidField",  # This doesn't exist
            "Value",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    # Should fail on field resolution, not during execution
    assert result.exit_code == 2
    assert "InvalidField" in result.output


def test_entry_field_operation_order(respx_mock: respx.MockRouter) -> None:
    """Operations execute in order: set/set-json → append → unset/unset-value.

    This test verifies that when combining operations on DIFFERENT fields,
    the order is correct:
    1. Set operations run first (Status field)
    2. Append operations run second (Tags field)
    3. Unset operations run last (Priority field)

    We verify this by checking the API calls are made in the correct sequence.
    """
    setup_list_mocks(respx_mock)

    # Track call order
    call_order: list[str] = []

    def track_field_values(_request):
        return Response(
            200,
            json=[
                {"id": 500, "fieldId": "field-100", "entityId": 224925, "value": "Old"},
                {"id": 501, "fieldId": "field-101", "entityId": 224925, "value": "Low"},
                {"id": 502, "fieldId": "field-102", "entityId": 224925, "value": "OldTag"},
            ],
        )

    def track_set(_request):
        call_order.append("set")
        return Response(
            200, json={"id": 600, "fieldId": "field-100", "entityId": 224925, "value": "New"}
        )

    def track_append(_request):
        call_order.append("append")
        return Response(
            200, json={"id": 601, "fieldId": "field-102", "entityId": 224925, "value": "NewTag"}
        )

    def track_delete(_request):
        call_order.append("unset")
        return Response(200, json={"success": True})

    respx_mock.get("https://api.affinity.co/field-values").mock(side_effect=track_field_values)
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(side_effect=track_set)
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-102"
    ).mock(side_effect=track_append)
    # Delete for set (existing Status value) and unset (Priority value)
    respx_mock.delete("https://api.affinity.co/field-values/500").mock(side_effect=track_delete)
    respx_mock.delete("https://api.affinity.co/field-values/501").mock(side_effect=track_delete)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            # Specify operations in "wrong" order to verify implementation reorders them
            "--unset",
            "Priority",  # Should run LAST (different field)
            "--append",
            "Tags",
            "NewTag",  # Should run SECOND
            "--set",
            "Status",
            "New",  # Should run FIRST
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 0, result.output
    # Verify order: set runs before append, append runs before unset
    # Note: set deletes existing first, so order includes delete calls
    assert call_order.index("set") < call_order.index("append")
    # The unset delete for Priority happens after append
    # Find the last unset (should be the Priority unset after refresh)
    append_index = call_order.index("append")
    # There should be at least one unset after append
    unset_after_append = [i for i, x in enumerate(call_order) if x == "unset" and i > append_index]
    assert len(unset_after_append) > 0, f"Expected unset after append, got: {call_order}"


def test_entry_field_field_name_like_id(respx_mock: respx.MockRouter) -> None:
    """Field literally named 'field-123' requires using actual field ID.

    If a field is named 'field-123' (unlikely but possible), the user must
    use the actual field ID to reference it, since 'field-123' pattern
    is interpreted as a field ID.
    """
    # Create field metadata with a field named "field-123"
    fields_with_weird_name = [
        *FIELDS_RESPONSE,
        {"id": "field-999", "name": "field-123", "valueType": 0, "allowsMultiple": False},
    ]
    respx_mock.get("https://api.affinity.co/v2/lists").mock(
        return_value=Response(200, json={"data": [LIST_RESPONSE], "pagination": {}})
    )
    respx_mock.get(f"https://api.affinity.co/v2/lists/{LIST_ID}/fields").mock(
        return_value=Response(200, json={"data": fields_with_weird_name, "pagination": {}})
    )

    runner = CliRunner()
    # Using "field-123" will be interpreted as a field ID, not a name
    # Since field-123 doesn't exist as an ID, it should error
    result = runner.invoke(
        cli,
        ["entry", "field", "Portfolio", str(ENTRY_ID), "--get", "field-123"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result.exit_code == 2
    assert "Field 'field-123' not found on list" in result.output

    # To access a field named "field-123", user must use the actual ID (field-999)
    respx_mock.get("https://api.affinity.co/field-values").mock(
        return_value=Response(
            200,
            json=[{"id": 500, "fieldId": "field-999", "entityId": 224925, "value": "test"}],
        )
    )

    result2 = runner.invoke(
        cli,
        ["--json", "entry", "field", "Portfolio", str(ENTRY_ID), "--get", "field-999"],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    assert result2.exit_code == 0, result2.output
    payload = json.loads(result2.output.strip())
    # The output key should be the field name, not the ID
    assert "field-123" in payload["data"]["fields"]


def test_entry_field_partial_failure(respx_mock: respx.MockRouter) -> None:
    """When API error occurs mid-operation, command fails but partial changes may persist.

    This test verifies behavior when:
    1. First field operation succeeds (data persisted in Affinity)
    2. Second field operation fails (API error)
    3. Command exits with error
    4. User is informed of the error

    Note: Affinity API doesn't support transactions, so partial updates remain.
    This is documented behavior - the user should check the entry state after errors.
    """
    setup_list_mocks(respx_mock)

    # Track what operations were attempted
    operations_attempted: list[str] = []

    def mock_field_values(_request):
        return Response(200, json=[])

    def mock_first_field_success(_request):
        operations_attempted.append("field-100")
        return Response(
            200, json={"id": 600, "fieldId": "field-100", "entityId": 224925, "value": "Active"}
        )

    def mock_second_field_failure(_request):
        operations_attempted.append("field-101")
        # Simulate API error (e.g., invalid value for field type)
        return Response(
            400,
            json={"error": {"message": "Invalid value for dropdown field"}},
        )

    respx_mock.get("https://api.affinity.co/field-values").mock(side_effect=mock_field_values)
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-100"
    ).mock(side_effect=mock_first_field_success)
    respx_mock.post(
        f"https://api.affinity.co/v2/lists/{LIST_ID}/list-entries/{ENTRY_ID}/fields/field-101"
    ).mock(side_effect=mock_second_field_failure)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "entry",
            "field",
            "Portfolio",
            str(ENTRY_ID),
            "--set",
            "Status",
            "Active",  # This will succeed
            "--set",
            "Priority",
            "InvalidValue",  # This will fail
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )

    # Command should fail
    assert result.exit_code != 0

    # Both operations were attempted (first succeeded before second failed)
    assert "field-100" in operations_attempted
    assert "field-101" in operations_attempted

    # Error message should be present
    assert "Invalid value" in result.output or "error" in result.output.lower()
