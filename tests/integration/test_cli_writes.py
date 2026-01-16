"""
CLI Write Integration Tests.

These tests verify CLI write commands against a live Affinity sandbox.
They focus on complex multi-step workflows that combine multiple operations.

Tests use the same safety protections as SDK integration tests:
- API key only from .sandbox.env
- Instance must be a sandbox (tenant name ends with 'sandbox')
- All test data is cleaned up

Usage:
    pytest tests/integration/test_cli_writes.py -m integration
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import pytest
from click.testing import CliRunner

from affinity.cli.main import cli

if TYPE_CHECKING:
    from affinity import Affinity
    from affinity.types import UserId

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration

# Test prefix for identifying test data
CLI_TEST_PREFIX = "CLI_INTEGRATION_TEST_"


def get_test_marker() -> str:
    """Generate a unique marker for this test run."""
    return f"{CLI_TEST_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}"


@dataclass
class CLIResult:
    """Result from running a CLI command."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def json(self) -> dict[str, Any]:
        """Parse stdout as JSON."""
        return cast(dict[str, Any], json.loads(self.stdout))

    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return self.exit_code == 0


def run_cli_with_retry(*args: str, api_key: str, retries: int = 3, delay: float = 1.0) -> CLIResult:
    """Run CLI command with retries for eventual consistency."""
    last_result = run_cli(*args, api_key=api_key)
    for _ in range(retries):
        if last_result.success:
            return last_result
        time.sleep(delay)
        last_result = run_cli(*args, api_key=api_key)
    return last_result


def run_cli(*args: str, api_key: str) -> CLIResult:
    """
    Run a CLI command with the given arguments.

    Args:
        *args: CLI arguments (e.g., "person", "create", "--first-name", "Test")
        api_key: Sandbox API key

    Returns:
        CLIResult with exit code, stdout, and stderr
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [*args, "--output", "json"],
        env={"AFFINITY_API_KEY": api_key},
        catch_exceptions=False,
    )

    return CLIResult(
        exit_code=result.exit_code,
        stdout=result.output,
        stderr="",
    )


# =============================================================================
# Test: Person CRUD Workflow
# =============================================================================


@pytest.mark.usefixtures("sandbox_client")
class TestPersonCRUDWorkflow:
    """Test person create → get → update → delete workflow via CLI."""

    def test_person_crud_cycle(self, sandbox_api_key: str) -> None:
        """Verify person CRUD operations work correctly via CLI."""
        marker = get_test_marker()
        person_id: int | None = None

        try:
            # Create
            result = run_cli(
                "person",
                "create",
                "--first-name",
                f"{marker}_First",
                "--last-name",
                f"{marker}_Last",
                "--email",
                f"{marker.lower()}@example.com",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Create failed: {result.stdout}"
            data = result.json
            assert data["data"] is not None and "person" in data["data"]
            person_id = data["data"]["person"]["id"]
            assert person_id is not None

            # Get (verify creation)
            result = run_cli("person", "get", str(person_id), api_key=sandbox_api_key)
            assert result.success, f"Get failed: {result.stdout}"
            data = result.json
            assert data["data"]["person"]["firstName"] == f"{marker}_First"
            assert data["data"]["person"]["lastName"] == f"{marker}_Last"

            # Update
            result = run_cli(
                "person",
                "update",
                str(person_id),
                "--first-name",
                f"{marker}_UpdatedFirst",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Update failed: {result.stdout}"
            data = result.json
            assert data["data"]["person"]["firstName"] == f"{marker}_UpdatedFirst"

            # Verify update persisted
            result = run_cli("person", "get", str(person_id), api_key=sandbox_api_key)
            assert result.success
            assert result.json["data"]["person"]["firstName"] == f"{marker}_UpdatedFirst"

        finally:
            # Cleanup: Delete
            if person_id:
                result = run_cli(
                    "person", "delete", str(person_id), "--yes", api_key=sandbox_api_key
                )
                # Don't fail test if cleanup fails, just log
                if not result.success:
                    print(f"Cleanup warning: Failed to delete person {person_id}")


# =============================================================================
# Test: Company CRUD Workflow
# =============================================================================


@pytest.mark.usefixtures("sandbox_client")
class TestCompanyCRUDWorkflow:
    """Test company create → get → update → delete workflow via CLI."""

    def test_company_crud_cycle(self, sandbox_api_key: str) -> None:
        """Verify company CRUD operations work correctly via CLI."""
        marker = get_test_marker()
        company_id: int | None = None

        try:
            # Create
            # Use dashes instead of underscores for valid domain format
            domain = marker.lower().replace("_", "-") + ".example.com"
            result = run_cli(
                "company",
                "create",
                "--name",
                f"{marker}_Company",
                "--domain",
                domain,
                api_key=sandbox_api_key,
            )
            assert result.success, f"Create failed: {result.stdout}"
            data = result.json
            assert data["data"] is not None and "company" in data["data"]
            company_id = data["data"]["company"]["id"]
            assert company_id is not None

            # Get (verify creation) - use retry for V1→V2 eventual consistency
            result = run_cli_with_retry("company", "get", str(company_id), api_key=sandbox_api_key)
            assert result.success, f"Get failed: {result.stdout}"
            data = result.json
            assert data["data"]["company"]["name"] == f"{marker}_Company"

            # Update
            result = run_cli(
                "company",
                "update",
                str(company_id),
                "--name",
                f"{marker}_UpdatedCompany",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Update failed: {result.stdout}"
            data = result.json
            assert data["data"]["company"]["name"] == f"{marker}_UpdatedCompany"

        finally:
            # Cleanup: Delete
            if company_id:
                result = run_cli(
                    "company", "delete", str(company_id), "--yes", api_key=sandbox_api_key
                )
                if not result.success:
                    print(f"Cleanup warning: Failed to delete company {company_id}")


# =============================================================================
# Test: Note CRUD Workflow
# =============================================================================


@pytest.mark.usefixtures("sandbox_client")
class TestNoteCRUDWorkflow:
    """Test note create → get → update → delete workflow via CLI."""

    def test_note_crud_on_person(self, sandbox_api_key: str) -> None:
        """Verify note CRUD operations on a person via CLI."""
        marker = get_test_marker()
        person_id: int | None = None
        note_id: int | None = None

        try:
            # First create a person to attach the note to
            result = run_cli(
                "person",
                "create",
                "--first-name",
                f"{marker}_NoteTest",
                "--last-name",
                "Test",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Person create failed: {result.stdout}"
            person_id = result.json["data"]["person"]["id"]

            # Create note
            result = run_cli(
                "note",
                "create",
                "--person-id",
                str(person_id),
                "--content",
                f"Test note content for {marker}",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Note create failed: {result.stdout}"
            data = result.json
            assert data["data"] is not None and "note" in data["data"]
            note_id = data["data"]["note"]["id"]

            # Get note
            result = run_cli("note", "get", str(note_id), api_key=sandbox_api_key)
            assert result.success, f"Note get failed: {result.stdout}"
            # Note: API may escape underscores, so check for base text
            assert "Test note content" in result.json["data"]["note"]["content"]

            # Update note
            result = run_cli(
                "note",
                "update",
                str(note_id),
                "--content",
                f"Updated note content for {marker}",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Note update failed: {result.stdout}"
            assert "Updated note content" in result.json["data"]["note"]["content"]

            # Delete note
            result = run_cli("note", "delete", str(note_id), "--yes", api_key=sandbox_api_key)
            assert result.success, f"Note delete failed: {result.stdout}"
            note_id = None  # Mark as deleted

        finally:
            # Cleanup
            if note_id:
                run_cli("note", "delete", str(note_id), "--yes", api_key=sandbox_api_key)
            if person_id:
                run_cli("person", "delete", str(person_id), "--yes", api_key=sandbox_api_key)


# =============================================================================
# Test: List Entry Workflow
# =============================================================================


class TestListEntryWorkflow:
    """Test list entry add → get → delete workflow via CLI."""

    def test_list_entry_add_and_delete(
        self, sandbox_api_key: str, sandbox_client: Affinity
    ) -> None:
        """Verify adding and removing entries from lists via CLI."""
        marker = get_test_marker()
        person_id: int | None = None
        entry_id: int | None = None

        # Find an existing person list to use
        lists_response = sandbox_client.lists.list(limit=100)
        person_list = None
        for lst in lists_response.data:
            if lst.type == 0:  # Person list
                person_list = lst
                break

        if not person_list:
            pytest.skip("No person list found in sandbox to test list entry operations")

        try:
            # Create a person to add to the list
            result = run_cli(
                "person",
                "create",
                "--first-name",
                f"{marker}_ListEntry",
                "--last-name",
                "Test",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Person create failed: {result.stdout}"
            person_id = result.json["data"]["person"]["id"]

            # Add person to list
            result = run_cli(
                "list",
                "entry",
                "add",
                str(person_list.id),
                "--person-id",
                str(person_id),
                api_key=sandbox_api_key,
            )
            assert result.success, f"Add entry failed: {result.stdout}"
            data = result.json
            assert data["data"] is not None and "listEntry" in data["data"]
            entry_id = data["data"]["listEntry"]["id"]

            # Get entry to verify
            result = run_cli(
                "list",
                "entry",
                "get",
                str(person_list.id),
                str(entry_id),
                api_key=sandbox_api_key,
            )
            assert result.success, f"Get entry failed: {result.stdout}"

            # Delete entry
            result = run_cli(
                "list",
                "entry",
                "delete",
                str(person_list.id),
                str(entry_id),
                "--yes",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Delete entry failed: {result.stdout}"
            entry_id = None  # Mark as deleted

        finally:
            # Cleanup
            if entry_id:
                run_cli(
                    "list",
                    "entry",
                    "delete",
                    str(person_list.id),
                    str(entry_id),
                    "--yes",
                    api_key=sandbox_api_key,
                )
            if person_id:
                run_cli("person", "delete", str(person_id), "--yes", api_key=sandbox_api_key)


# =============================================================================
# Test: Reminder CRUD Workflow
# =============================================================================


@pytest.mark.usefixtures("sandbox_client")
class TestReminderCRUDWorkflow:
    """Test reminder create → get → update → delete workflow via CLI."""

    def test_reminder_crud_cycle(self, sandbox_api_key: str, sandbox_user_id: UserId) -> None:
        """Verify reminder CRUD operations via CLI."""
        marker = get_test_marker()
        person_id: int | None = None
        reminder_id: int | None = None

        try:
            # Create a person to attach reminder to
            result = run_cli(
                "person",
                "create",
                "--first-name",
                f"{marker}_ReminderTest",
                "--last-name",
                "Test",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Person create failed: {result.stdout}"
            person_id = result.json["data"]["person"]["id"]

            # Create reminder (due in 7 days) - using relative date format
            result = run_cli(
                "reminder",
                "create",
                "--person-id",
                str(person_id),
                "--owner-id",
                str(sandbox_user_id),
                "--type",
                "one-time",
                "--due-date",
                "+7d",
                "--content",
                f"Test reminder for {marker}",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Reminder create failed: {result.stdout}"
            data = result.json
            assert data["data"] is not None and "reminder" in data["data"]
            reminder_id = data["data"]["reminder"]["id"]

            # Get reminder
            result = run_cli("reminder", "get", str(reminder_id), api_key=sandbox_api_key)
            assert result.success, f"Reminder get failed: {result.stdout}"

            # Update reminder
            result = run_cli(
                "reminder",
                "update",
                str(reminder_id),
                "--content",
                f"Updated reminder for {marker}",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Reminder update failed: {result.stdout}"

            # Delete reminder
            result = run_cli(
                "reminder", "delete", str(reminder_id), "--yes", api_key=sandbox_api_key
            )
            assert result.success, f"Reminder delete failed: {result.stdout}"
            reminder_id = None

        finally:
            if reminder_id:
                run_cli(
                    "reminder",
                    "delete",
                    str(reminder_id),
                    "--yes",
                    api_key=sandbox_api_key,
                )
            if person_id:
                run_cli("person", "delete", str(person_id), "--yes", api_key=sandbox_api_key)


# =============================================================================
# Test: CLI Output Format Verification
# =============================================================================


@pytest.mark.usefixtures("sandbox_client")
class TestCLIOutputFormats:
    """Test that CLI output formats are correct for write operations."""

    def test_create_output_includes_context(self, sandbox_api_key: str) -> None:
        """Verify create command output includes proper context."""
        marker = get_test_marker()
        person_id: int | None = None

        try:
            result = run_cli(
                "person",
                "create",
                "--first-name",
                f"{marker}_Context",
                "--last-name",
                "Test",
                api_key=sandbox_api_key,
            )
            assert result.success, f"Create failed: {result.stdout}"
            data = result.json
            person_id = data["data"]["person"]["id"]

            # Verify CLI output structure
            assert "ok" in data and data["ok"] is True
            assert "data" in data and data["data"] is not None
            assert "person" in data["data"]
            assert "meta" in data
            assert "command" in data
            assert data["command"]["name"] == "person create"

        finally:
            if person_id:
                run_cli("person", "delete", str(person_id), "--yes", api_key=sandbox_api_key)

    def test_error_output_format(self, sandbox_api_key: str) -> None:
        """Verify error responses have correct format."""
        # Try to get a non-existent person
        result = run_cli("person", "get", "999999999", api_key=sandbox_api_key)

        assert not result.success
        assert result.exit_code == 4  # Not found exit code

        # Error output should be valid JSON
        data = result.json
        assert "error" in data
        assert "type" in data["error"]


# =============================================================================
# Test: Client-Side Validation
# =============================================================================


class TestClientSideValidation:
    """Test that client-side validation catches errors before API call."""

    def test_domain_underscore_rejected_with_hint(self, sandbox_api_key: str) -> None:
        """Verify domain with underscore is rejected client-side with helpful hint."""
        result = run_cli(
            "company",
            "create",
            "--name",
            "Test Company",
            "--domain",
            "test_company.example.com",
            api_key=sandbox_api_key,
        )

        assert not result.success
        assert result.exit_code == 2  # Usage error exit code

        data = result.json
        assert data["ok"] is False
        assert "error" in data
        assert "underscore" in data["error"]["message"].lower()
        # Verify hint suggests dash replacement
        assert data["error"]["hint"] is not None
        assert "test-company.example.com" in data["error"]["hint"]

    def test_domain_url_rejected_with_hint(self, sandbox_api_key: str) -> None:
        """Verify URL passed as domain is rejected client-side with helpful hint."""
        result = run_cli(
            "company",
            "create",
            "--name",
            "Test Company",
            "--domain",
            "https://example.com/path",
            api_key=sandbox_api_key,
        )

        assert not result.success
        assert result.exit_code == 2  # Usage error exit code

        data = result.json
        assert data["ok"] is False
        assert "error" in data
        assert "url" in data["error"]["message"].lower()
        # Verify hint extracts domain
        assert data["error"]["hint"] is not None
        assert "example.com" in data["error"]["hint"]
