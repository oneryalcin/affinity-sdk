"""
Integration tests to verify CLI JSON output is JSON-safe.

These tests ensure that all CLI commands with --json flag produce
valid JSON that can be parsed and doesn't contain Python-specific types.

## What This Tests

This test suite verifies Phase 1 of the CLI JSON Output Resolution Plan:
- All model_dump() calls use mode="json" to convert datetime to ISO strings
- All model_dump() calls use exclude_none=True for consistent null handling
- CLI commands with --json output produce valid, parseable JSON
- No Python-specific types (datetime, custom objects) leak into JSON output

## Commands Affected by Serialization Fix (19 locations across 9 files)

The following CLI commands were fixed to use proper JSON serialization:

1. **person_cmds.py** (2 locations)
   - `affinity person create` (line 1302)
   - `affinity person update` (line 1356)

2. **company_cmds.py** (3 locations)
   - `affinity company get` (line 939)
   - `affinity company create` (line 1375)
   - `affinity company update` (line 1421)

3. **opportunity_cmds.py** (3 locations)
   - `affinity opportunity get` (line 228)
   - `affinity opportunity create` (line 395)
   - `affinity opportunity update` (line 458)

4. **list_cmds.py** (6 locations)
   - `affinity list create` (line 208)
   - `affinity list view` (lines 237-238)
   - `affinity list entry add` (line 768)
   - `affinity list entry update-field` (line 841)
   - `affinity list entry batch-update` (line 882)

5. **field_cmds.py** (1 location) - `affinity field ls` (line 32)
6. **field_value_cmds.py** (1 location) - `affinity field-value ls` (line 20)
7. **relationship_strength_cmds.py** (1 location) - `affinity relationship-strength ls` (line 23)
8. **task_cmds.py** (1 location) - `affinity task get` (line 17)
9. **whoami_cmd.py** (1 location) - `affinity whoami` (line 17)

## Critical Entities with Datetime Fields

These entities have datetime fields that WILL cause TypeError without mode="json":
- **ListEntry.created_at** (required field)
- **Opportunity.created_at, updated_at** (optional fields)
- **Note.created_at** (required field)

Commands returning these entities were failing with:
`TypeError: Object of type datetime is not JSON serializable`

## CI Integration

These tests run automatically as part of the pytest suite:
- Included in: `pytest tests/` (all tests)
- Included in: `pytest tests/ -k cli` (CLI-specific tests)
- Included in: `pytest tests/test_cli_json_safety.py` (this file only)

## Test Coverage

This file provides both:
1. Unit tests for JSON serialization safety (model-level)
2. End-to-end CLI tests with --json flag (command-level)

Additional comprehensive CLI testing is covered by:
- test_cli_opportunity_cmds.py (8 tests)
- test_cli_write_ops.py (5 tests covering CRUD operations)
- test_cli_company_get.py (14 tests)
- test_cli_person_get.py (3 tests)
- Plus 190+ other CLI tests
"""

import json
from datetime import datetime, timezone
from typing import Any

import httpx
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

from affinity import Affinity
from affinity.cli.main import cli
from affinity.models.entities import ListEntry, Person

if respx is None:  # pragma: no cover
    pytest.skip("respx is not installed", allow_module_level=True)


def verify_json_safe(data: Any, path: str = "root") -> None:
    """
    Recursively verify data structure contains only JSON-safe types.

    Raises:
        AssertionError: If non-JSON-safe types found
    """
    if isinstance(data, dict):
        for key, value in data.items():
            verify_json_safe(value, f"{path}.{key}")
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            verify_json_safe(item, f"{path}[{idx}]")
    elif not isinstance(data, (str, int, float, bool, type(None))):
        raise AssertionError(f"Non-JSON-safe type at {path}: {type(data).__name__} = {data}")


class TestCLIJSONSafety:
    """Test that all CLI commands produce JSON-safe output."""

    def test_model_dump_produces_json_safe_output(self):
        """Verify model_dump with mode='json' produces JSON-safe output."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": 123,
                    "first_name": "John",
                    "last_name": "Doe",
                    "emails": ["john@example.com"],
                },
            )

        transport = httpx.MockTransport(handler)

        with Affinity(api_key="test-key", max_retries=0, transport=transport) as client:
            person = client.persons.get(123)
            # This is what CLI commands should do:
            payload = person.model_dump(by_alias=True, mode="json", exclude_none=True)

            # Should be JSON-serializable
            json_str = json.dumps(payload)
            parsed = json.loads(json_str)

            # Should contain only JSON-safe types
            verify_json_safe(parsed)

    def test_datetime_fields_serialize_correctly(self):
        """Verify datetime fields are serialized as ISO strings, not Python objects."""
        # Test with ListEntry which has required datetime field and is returned by CLI commands
        entry = ListEntry(
            id=123,
            list_id=456,
            creator_id=789,
            entity_id=999,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        # mode="json" should convert datetime to ISO string
        payload = entry.model_dump(by_alias=True, mode="json", exclude_none=True)

        # Should be JSON-serializable (would fail if datetime wasn't converted)
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        # createdAt should be a string, not datetime object
        assert isinstance(parsed.get("createdAt"), str)
        assert parsed["createdAt"] == "2025-01-01T12:00:00Z"
        verify_json_safe(parsed)

    def test_exclude_none_removes_null_fields(self):
        """Verify exclude_none=True removes None fields from output."""
        person = Person(
            id=123,
            first_name="John",
            last_name="Doe",
            emails=["john@example.com"],
            # Leave optional fields as None
        )

        # Without exclude_none, None fields appear
        with_none = person.model_dump(by_alias=True, mode="json")
        assert any(v is None for v in with_none.values())

        # With exclude_none, None fields are removed
        without_none = person.model_dump(by_alias=True, mode="json", exclude_none=True)
        assert not any(v is None for v in without_none.values())

    def test_list_entry_datetime_serialization(self):
        """Verify ListEntry.created_at is serialized as ISO string."""
        entry = ListEntry(
            id=123,
            list_id=456,
            creator_id=789,
            entity_id=999,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        payload = entry.model_dump(by_alias=True, mode="json", exclude_none=True)

        # Should be JSON-serializable
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        # createdAt should be a string, not datetime object
        assert isinstance(parsed.get("createdAt"), str)
        assert parsed["createdAt"] == "2025-01-01T12:00:00Z"
        verify_json_safe(parsed)


class TestCLIEndToEndJSONSafety:
    """End-to-end tests verifying CLI commands with --json flag produce valid JSON."""

    def test_opportunity_get_json_safe(self, respx_mock: respx.MockRouter) -> None:
        """Verify opportunity get command with --json flag produces valid JSON."""
        # Mock API response with datetime fields
        respx_mock.get("https://api.affinity.co/v2/opportunities/123").mock(
            return_value=Response(
                200,
                json={
                    "id": 123,
                    "name": "Series A",
                    "listId": 41780,
                    "createdAt": "2025-01-15T10:30:00Z",
                    "updatedAt": "2025-01-20T14:45:00Z",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "opportunity", "get", "123"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        # Command should succeed
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Output should be valid JSON
        parsed = json.loads(result.output.strip())

        # Verify structure
        assert "data" in parsed
        assert "opportunity" in parsed["data"]

        # Verify datetime fields are strings
        opp = parsed["data"]["opportunity"]
        if "createdAt" in opp:
            assert isinstance(opp["createdAt"], str)
        if "updatedAt" in opp:
            assert isinstance(opp["updatedAt"], str)

        # Verify entire structure is JSON-safe
        verify_json_safe(parsed)

    def test_company_get_json_safe(self, respx_mock: respx.MockRouter) -> None:
        """Verify company get command with --json flag produces valid JSON."""
        respx_mock.get("https://api.affinity.co/v2/companies/789").mock(
            return_value=Response(
                200,
                json={
                    "id": 789,
                    "name": "Acme Corp",
                    "domain": "acme.com",
                },
            )
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json", "company", "get", "789"],
            env={"AFFINITY_API_KEY": "test-key"},
        )

        # Command should succeed
        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Output should be valid JSON
        parsed = json.loads(result.output.strip())

        # Verify entire structure is JSON-safe
        verify_json_safe(parsed)
