"""
Pytest wrapper for SDK write integration tests.

This module provides a pytest entry point for the write test suite.
The actual tests are in test_sdk_writes.py and can also be run directly:

    python tests/integration/test_sdk_writes.py

This wrapper:
- Verifies sandbox environment
- Runs the write test suite programmatically
- Reports results via pytest assertions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from affinity import Affinity
    from affinity.types import UserId

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestSDKWrites:
    """
    Pytest wrapper for the SDK write test suite.

    Note: The full write test suite is comprehensive and includes cleanup.
    For interactive use with prompts, run directly:
        python tests/integration/test_sdk_writes.py
    """

    def test_person_crud(self, sandbox_client: Affinity) -> None:
        """Test person create, read, update, delete cycle."""
        from tests.integration.test_sdk_writes import RunConfig, verify_person_crud

        config = RunConfig.create(
            owner_id=sandbox_client.auth.whoami().user.id,
            beta_enabled=False,
        )
        result = verify_person_crud(sandbox_client, config)
        assert result is True, "Person CRUD test failed"

    def test_company_crud(self, sandbox_client: Affinity) -> None:
        """Test company create, read, update, delete cycle."""
        from tests.integration.test_sdk_writes import RunConfig, verify_company_crud

        config = RunConfig.create(
            owner_id=sandbox_client.auth.whoami().user.id,
            beta_enabled=False,
        )
        result = verify_company_crud(sandbox_client, config)
        assert result is True, "Company CRUD test failed"

    def test_list_creation(self, sandbox_client: Affinity) -> None:
        """Test list creation for all entity types."""
        from tests.integration.test_sdk_writes import RunConfig, verify_list_create_all_types

        config = RunConfig.create(
            owner_id=sandbox_client.auth.whoami().user.id,
            beta_enabled=False,
        )
        # Note: Lists cannot be deleted via API, so test lists will remain
        test_lists = verify_list_create_all_types(sandbox_client, config)
        assert test_lists.person_list.id is not None
        assert test_lists.company_list.id is not None
        assert test_lists.opportunity_list.id is not None

    def test_webhook_crud(self, sandbox_client: Affinity) -> None:
        """Test webhook create, read, update, delete cycle."""
        from tests.integration.test_sdk_writes import RunConfig, verify_webhook_crud

        config = RunConfig.create(
            owner_id=sandbox_client.auth.whoami().user.id,
            beta_enabled=False,
        )
        result = verify_webhook_crud(sandbox_client, config)
        assert result is True, "Webhook CRUD test failed"


class TestSDKWritesFull:
    """
    Run the full write test suite as a single pytest test.

    This is useful for CI where you want a single pass/fail result
    for all write operations. For granular results, use TestSDKWrites above.
    """

    @pytest.mark.slow
    def test_full_write_suite(
        self,
        sandbox_client: Affinity,
        sandbox_user_id: UserId,
    ) -> None:
        """
        Run the complete write test suite.

        This test:
        1. Creates test entities (persons, companies, lists, opportunities)
        2. Tests CRUD operations on all entity types
        3. Tests field operations, notes, reminders, interactions
        4. Tests file uploads and webhooks
        5. Cleans up all test data

        Note: This test takes several minutes to complete.
        """
        from tests.integration.test_sdk_writes import (
            CleanupItem,
            Fixtures,
            RunConfig,
            cleanup_test_data,
            create_persistent_fixtures,
            create_persistent_opportunity,
            verify_company_crud,
            verify_company_list_entry_operations,
            verify_company_merge,
            verify_file_upload_bytes,
            verify_file_upload_path,
            verify_file_verification,
            verify_global_field_operations,
            verify_interaction_crud,
            verify_list_create_all_types,
            verify_list_specific_field_operations,
            verify_note_on_company_crud,
            verify_note_on_opportunity_crud,
            verify_note_on_person_crud,
            verify_one_time_reminder_crud,
            verify_opportunity_crud,
            verify_person_crud,
            verify_person_list_entry_operations,
            verify_person_merge,
            verify_recurring_reminder_crud,
            verify_webhook_crud,
        )

        config = RunConfig.create(owner_id=sandbox_user_id, beta_enabled=False)
        results: dict[str, bool] = {}
        cleanup_items: list[CleanupItem] = []
        fixtures = Fixtures()

        try:
            # Group 1: CRUD Verification
            results["verify_person_crud"] = verify_person_crud(sandbox_client, config)
            results["verify_company_crud"] = verify_company_crud(sandbox_client, config)

            # Group 2: List Creation + Persistent Fixtures
            test_lists = verify_list_create_all_types(sandbox_client, config)
            fixtures = create_persistent_fixtures(sandbox_client, config, cleanup_items)
            results["verify_person_list_entry_operations"] = verify_person_list_entry_operations(
                sandbox_client, test_lists.person_list.id, fixtures.person_id
            )
            results["verify_company_list_entry_operations"] = verify_company_list_entry_operations(
                sandbox_client, test_lists.company_list.id, fixtures.company_id
            )

            # Group 3: Opportunity CRUD
            results["verify_opportunity_crud"] = verify_opportunity_crud(
                sandbox_client, config, test_lists.opportunity_list.id
            )
            create_persistent_opportunity(
                sandbox_client, config, test_lists.opportunity_list.id, cleanup_items, fixtures
            )

            # Group 4: Field Operations
            results["verify_global_field_operations"] = verify_global_field_operations(
                sandbox_client, config, fixtures.person_id
            )
            results["verify_list_specific_field_operations"] = (
                verify_list_specific_field_operations(
                    sandbox_client, config, test_lists.person_list.id, fixtures.person_id
                )
            )

            # Group 5: Notes and Reminders
            results["verify_note_on_person_crud"] = verify_note_on_person_crud(
                sandbox_client, config, fixtures.person_id
            )
            results["verify_note_on_company_crud"] = verify_note_on_company_crud(
                sandbox_client, config, fixtures.company_id
            )
            results["verify_note_on_opportunity_crud"] = verify_note_on_opportunity_crud(
                sandbox_client, config, fixtures.opportunity_id
            )
            results["verify_one_time_reminder_crud"] = verify_one_time_reminder_crud(
                sandbox_client, config, fixtures.person_id
            )
            results["verify_recurring_reminder_crud"] = verify_recurring_reminder_crud(
                sandbox_client, config, fixtures.company_id
            )

            # Group 6: Interactions
            results["verify_interaction_crud"] = verify_interaction_crud(
                sandbox_client, config, fixtures.person_id
            )

            # Group 7: File Operations
            results["verify_file_upload_bytes"] = verify_file_upload_bytes(
                sandbox_client, config, fixtures.person_id
            )
            results["verify_file_upload_path"] = verify_file_upload_path(
                sandbox_client, config, fixtures.company_id
            )
            results["verify_file_verification"] = verify_file_verification(
                sandbox_client, config, fixtures.person_id, fixtures.company_id
            )

            # Group 8: Webhooks
            results["verify_webhook_crud"] = verify_webhook_crud(sandbox_client, config)

            # Group 9: Beta Features (skip - require beta enabled)
            results["verify_person_merge"] = verify_person_merge(sandbox_client, config)
            results["verify_company_merge"] = verify_company_merge(sandbox_client, config)

        finally:
            # Always cleanup
            cleanup_test_data(sandbox_client, cleanup_items)

        # Assert all tests passed
        failed = [name for name, passed in results.items() if not passed]
        assert not failed, f"Failed tests: {failed}"
