#!/usr/bin/env python
"""
Setup script for query-list-export-parity integration tests.

This script creates the test data needed for comprehensive query testing.
Run this ONCE to populate the sandbox with test data, then run the tests
repeatedly (they are read-only queries).

Usage:
    python tests/integration/setup_query_parity_data.py

The script will:
1. Verify the API key is for a sandbox instance
2. Create a test list "QUERY_PARITY_TEST_Pipeline"
3. Create test persons and companies
4. Add persons to the list
5. Output the created IDs for reference

Requirements:
- .sandbox.env file with AFFINITY_API_KEY
- Sandbox instance (tenant name must end with "sandbox")
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from affinity import Affinity
from affinity.exceptions import AffinityError
from affinity.models.entities import CompanyCreate, ListCreate, PersonCreate
from affinity.models.types import ListType

# Test data prefix - all test data uses this for identification
TEST_PREFIX = "QUERY_PARITY_TEST_"

# Output file for test data IDs
OUTPUT_FILE = Path(__file__).parent / "query_parity_test_data.json"


def load_sandbox_api_key() -> str | None:
    """Load API key from .sandbox.env file."""
    possible_paths = [
        Path(__file__).parent.parent.parent / ".sandbox.env",
        Path.cwd() / ".sandbox.env",
    ]

    for env_file in possible_paths:
        if env_file.exists():
            with env_file.open() as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("AFFINITY_API_KEY="):
                        return line.split("=", 1)[1].strip()
    return None


def verify_sandbox(client: Affinity) -> str:
    """Verify this is a sandbox instance. Returns tenant name."""
    whoami = client.auth.whoami()
    tenant_name = whoami.tenant.name

    if not tenant_name.lower().endswith("sandbox"):
        raise RuntimeError(
            f"SAFETY CHECK FAILED: Tenant '{tenant_name}' does not end with 'sandbox'. "
            f"This script only runs against sandbox instances."
        )

    return tenant_name


@dataclass
class TestData:
    """Container for all created test data."""

    list_id: int | None = None
    list_name: str | None = None
    person_ids: list[int] | None = None
    company_ids: list[int] | None = None
    entry_ids: list[int] | None = None
    interaction_ids: list[int] | None = None
    status_field_id: int | None = None
    priority_field_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "list_id": self.list_id,
            "list_name": self.list_name,
            "person_ids": self.person_ids,
            "company_ids": self.company_ids,
            "entry_ids": self.entry_ids,
            "interaction_ids": self.interaction_ids,
            "status_field_id": self.status_field_id,
            "priority_field_id": self.priority_field_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "test_prefix": TEST_PREFIX,
        }


def find_existing_test_list(client: Affinity, list_name: str) -> int | None:
    """Check if test list already exists."""
    for lst in client.lists.iter():
        if lst.name == list_name:
            return lst.id
    return None


def create_test_list(client: Affinity, test_data: TestData) -> None:
    """Create test list or find existing one."""
    list_name = f"{TEST_PREFIX}Pipeline"  # Person list for contacts
    test_data.list_name = list_name

    existing_id = find_existing_test_list(client, list_name)
    if existing_id:
        print(f"  Found existing list: {list_name} (ID: {existing_id})")
        test_data.list_id = existing_id
        return

    print(f"  Creating list: {list_name}")
    try:
        # Lists are created via V1 API - use PERSON type so we can add persons
        list_data = ListCreate(name=list_name, type=ListType.PERSON, is_public=True)
        result = client.lists.create(list_data)
        test_data.list_id = result.id
        print(f"    Created list ID: {test_data.list_id}")
    except AffinityError as e:
        if "already exists" in str(e).lower():
            # List already exists, find it
            existing_id = find_existing_test_list(client, list_name)
            if existing_id:
                test_data.list_id = existing_id
                print(f"    List already exists, ID: {existing_id}")
            else:
                raise
        else:
            raise


def find_existing_test_persons(client: Affinity, prefix: str) -> list[int]:
    """Find existing test persons."""
    person_ids = []
    for person in client.persons.iter():
        if person.first_name and person.first_name.startswith(prefix):
            person_ids.append(person.id)
    return person_ids


def create_test_persons(client: Affinity, test_data: TestData) -> None:
    """Create test persons or find existing ones."""
    prefix = TEST_PREFIX

    existing = find_existing_test_persons(client, prefix)
    if existing:
        print(f"  Found {len(existing)} existing test persons")
        test_data.person_ids = existing
        return

    print("  Creating test persons...")
    person_ids = []

    persons_data = [
        {
            "first_name": f"{prefix}Alice",
            "last_name": "Anderson",
            "emails": [f"{prefix.lower()}alice@example.com"],
        },
        {
            "first_name": f"{prefix}Bob",
            "last_name": "Baker",
            "emails": [f"{prefix.lower()}bob@example.com"],
        },
        {
            "first_name": f"{prefix}Charlie",
            "last_name": "Chen",
            "emails": [f"{prefix.lower()}charlie@example.com"],
        },
        {
            "first_name": f"{prefix}Diana",
            "last_name": "Davis",
            "emails": [f"{prefix.lower()}diana@example.com"],
        },
        {
            "first_name": f"{prefix}Eve",
            "last_name": "Evans",
            "emails": [f"{prefix.lower()}eve@example.com"],
        },
    ]

    for data in persons_data:
        try:
            person_data = PersonCreate(**data)
            result = client.persons.create(person_data)
            person_ids.append(result.id)
            print(f"    Created person: {data['first_name']} (ID: {result.id})")
            time.sleep(0.5)  # Rate limiting
        except AffinityError as e:
            if "already exists" in str(e).lower():
                print(f"    Person {data['first_name']} already exists, skipping")
            else:
                raise

    test_data.person_ids = person_ids


def find_existing_test_companies(client: Affinity, prefix: str) -> list[int]:
    """Find existing test companies."""
    company_ids = []
    for company in client.companies.iter():
        if company.name and company.name.startswith(prefix):
            company_ids.append(company.id)
    return company_ids


def create_test_companies(client: Affinity, test_data: TestData) -> None:
    """Create test companies or find existing ones."""
    prefix = TEST_PREFIX

    existing = find_existing_test_companies(client, prefix)
    if existing:
        print(f"  Found {len(existing)} existing test companies")
        test_data.company_ids = existing
        return

    print("  Creating test companies...")
    company_ids = []

    companies_data = [
        {"name": f"{prefix}Acme Corp", "domain": "qpt-acme-test.com"},
        {"name": f"{prefix}Beta Inc", "domain": "qpt-beta-test.io"},
        {"name": f"{prefix}Gamma LLC", "domain": "qpt-gamma-test.net"},
    ]

    for data in companies_data:
        try:
            company_data = CompanyCreate(**data)
            result = client.companies.create(company_data)
            company_ids.append(result.id)
            print(f"    Created company: {data['name']} (ID: {result.id})")
            time.sleep(0.5)
        except AffinityError as e:
            if "already exists" in str(e).lower():
                print(f"    Company {data['name']} already exists, skipping")
            else:
                raise

    test_data.company_ids = company_ids


def get_or_create_list_fields(client: Affinity, test_data: TestData) -> None:
    """Get or create custom fields for the test list."""
    if not test_data.list_id:
        return

    print("  Checking list fields...")

    # Get existing fields for this list
    fields = client.fields.list()
    list_fields = [f for f in fields if f.list_id == test_data.list_id]

    status_field = next((f for f in list_fields if f.name == "Status"), None)
    priority_field = next((f for f in list_fields if f.name == "Priority"), None)

    if status_field:
        test_data.status_field_id = status_field.id
        print(f"    Found Status field (ID: {status_field.id})")
    else:
        print("    Status field not found - will use default list fields")

    if priority_field:
        test_data.priority_field_id = priority_field.id
        print(f"    Found Priority field (ID: {priority_field.id})")


def add_entries_to_list(client: Affinity, test_data: TestData) -> None:
    """Add persons and companies to the test list."""
    if not test_data.list_id:
        print("  Skipping list entries (no list)")
        return

    print("  Adding entries to list...")
    entry_ids = []

    # Check for existing entries
    existing_entries = list(client.lists.entries(test_data.list_id).iter())
    # entity is a nested object with .id
    existing_entity_ids = {e.entity.id for e in existing_entries if e.entity}
    print(f"    Found {len(existing_entries)} existing entries")

    # Add persons as entries (person list only accepts persons)
    if test_data.person_ids:
        for person_id in test_data.person_ids:  # Add all persons
            if person_id in existing_entity_ids:
                # Find existing entry ID
                entry = next(
                    (e for e in existing_entries if e.entity and e.entity.id == person_id), None
                )
                if entry:
                    entry_ids.append(entry.id)
                continue

            try:
                entry = client.lists.entries(test_data.list_id).add_person(person_id)
                entry_ids.append(entry.id)
                print(f"    Added person {person_id} as entry {entry.id}")
                time.sleep(0.3)
            except AffinityError as e:
                if "already" in str(e).lower():
                    print(f"    Person {person_id} already in list")
                else:
                    print(f"    Warning: Could not add person {person_id}: {e}")

    # Include existing entry IDs if we didn't add new ones
    if not entry_ids and existing_entries:
        entry_ids = [e.id for e in existing_entries[:5]]

    test_data.entry_ids = entry_ids


def create_test_interactions(_client: Affinity, test_data: TestData) -> None:
    """Create test interactions for persons."""
    if not test_data.person_ids or len(test_data.person_ids) < 2:
        print("  Skipping interactions (not enough persons)")
        return

    print("  Skipping interactions (requires internal team members)")
    print("    Note: Interactions require at least 1 internal and 1 external person")
    print("    Test data will work without interactions for basic query tests")
    test_data.interaction_ids = []


def save_test_data(test_data: TestData) -> None:
    """Save test data IDs to JSON file."""
    print(f"\nSaving test data to {OUTPUT_FILE}...")
    with OUTPUT_FILE.open("w") as f:
        json.dump(test_data.to_dict(), f, indent=2)
    print("  Done!")


def main() -> int:
    """Main setup function."""
    print("=" * 60)
    print("Query-List-Export Parity Test Data Setup")
    print("=" * 60)

    # Load API key
    api_key = load_sandbox_api_key()
    if not api_key:
        print("\nERROR: No .sandbox.env file found with AFFINITY_API_KEY")
        print("Create .sandbox.env in project root with your sandbox API key.")
        return 1

    # Create client
    print("\nConnecting to Affinity...")
    client = Affinity(api_key=api_key)

    try:
        # Verify sandbox
        tenant_name = verify_sandbox(client)
        print(f"  Connected to: {tenant_name}")

        # Create test data
        test_data = TestData()

        print("\nStep 1: Create test list")
        create_test_list(client, test_data)

        print("\nStep 2: Create test persons")
        create_test_persons(client, test_data)

        print("\nStep 3: Create test companies")
        create_test_companies(client, test_data)

        print("\nStep 4: Get/create list fields")
        get_or_create_list_fields(client, test_data)

        print("\nStep 5: Add entries to list")
        add_entries_to_list(client, test_data)

        print("\nStep 6: Create test interactions")
        create_test_interactions(client, test_data)

        # Save test data
        save_test_data(test_data)

        print("\n" + "=" * 60)
        print("Setup Complete!")
        print("=" * 60)
        print("\nTest data summary:")
        print(f"  List: {test_data.list_name} (ID: {test_data.list_id})")
        print(f"  Persons: {len(test_data.person_ids or [])}")
        print(f"  Companies: {len(test_data.company_ids or [])}")
        print(f"  List entries: {len(test_data.entry_ids or [])}")
        print(f"  Interactions: {len(test_data.interaction_ids or [])}")
        print(f"\nTest data saved to: {OUTPUT_FILE}")
        print("\nYou can now run the integration tests:")
        print("  pytest tests/integration/test_query_parity_integration.py -m integration")

        return 0

    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
