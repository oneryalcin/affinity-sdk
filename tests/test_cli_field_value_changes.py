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


def test_field_value_changes_ls_by_person_id(respx_mock: respx.MockRouter) -> None:
    """List field value changes for a person."""
    # V1 API returns bare array with snake_case keys; HTTP client normalizes to {"data": [...]}
    # Note: V1 returns numeric field_id; FieldId class auto-converts to "field-{int}" format
    respx_mock.get("https://api.affinity.co/field-value-changes").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 101,
                    "field_id": 123,  # V1 returns numeric; model converts to "field-123"
                    "entity_id": 456,
                    "list_entry_id": None,
                    "action_type": 2,
                    "value": "Closed",
                    "changed_at": "2024-01-15T10:30:00Z",
                    "changer": {"id": 10, "type": 0, "first_name": "Jane", "last_name": "Doe"},
                }
            ],
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "field-value-changes", "ls", "--field-id", "field-123", "--person-id", "456"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["fieldValueChanges"][0]["id"] == 101
    # Output uses camelCase aliases (by_alias=True)
    assert payload["data"]["fieldValueChanges"][0]["fieldId"] == "field-123"
    assert payload["data"]["fieldValueChanges"][0]["actionType"] == 2


def test_field_value_changes_ls_by_company_id(respx_mock: respx.MockRouter) -> None:
    """List field value changes for a company."""
    respx_mock.get("https://api.affinity.co/field-value-changes").mock(
        return_value=Response(200, json=[])
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--json", "field-value-changes", "ls", "--field-id", "field-123", "--company-id", "789"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["fieldValueChanges"] == []


def test_field_value_changes_ls_with_action_type(respx_mock: respx.MockRouter) -> None:
    """Filter field value changes by action type."""
    respx_mock.get("https://api.affinity.co/field-value-changes").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 102,
                    "field_id": 123,
                    "entity_id": 456,
                    "action_type": 0,
                    "value": "Open",
                    "changed_at": "2024-01-10T09:00:00Z",
                }
            ],
        )
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "field-value-changes",
            "ls",
            "--field-id",
            "field-123",
            "--person-id",
            "456",
            "--action-type",
            "create",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["data"]["fieldValueChanges"][0]["actionType"] == 0


def test_field_value_changes_ls_requires_exactly_one_selector() -> None:
    """Error when no entity selector provided."""
    runner = CliRunner()

    # No selector
    result = runner.invoke(
        cli,
        ["--json", "field-value-changes", "ls", "--field-id", "field-123"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 2
    assert "exactly one" in result.output.lower() or "exactly one" in str(result.exception).lower()

    # Multiple selectors
    result = runner.invoke(
        cli,
        [
            "--json",
            "field-value-changes",
            "ls",
            "--field-id",
            "field-123",
            "--person-id",
            "1",
            "--company-id",
            "2",
        ],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 2


def test_field_value_changes_ls_missing_field_id() -> None:
    """Error when --field-id is not provided (Click validation)."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["field-value-changes", "ls", "--person-id", "456"],
        env={"AFFINITY_API_KEY": "test-key"},
    )
    assert result.exit_code == 2
    assert "field-id" in result.output.lower()
