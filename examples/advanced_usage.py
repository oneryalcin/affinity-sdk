"""
Advanced usage examples for the Affinity Python SDK.

This file demonstrates more complex use cases including:
- Batch operations
- Field filtering and selection
- Working with enriched data
- Pagination strategies
- Error handling patterns
- Integration workflows
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from affinity import (
    Affinity,
    AffinityError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from affinity.models import NoteCreate, ReminderCreate
from affinity.types import (
    CompanyId,
    FieldId,
    FieldType,
    FieldValueType,
    ListId,
    ListType,
    NoteType,
    PersonId,
    PersonType,
    ReminderType,
    UserId,
)


def get_api_key() -> str:
    """Get API key from environment or prompt."""
    api_key = os.environ.get("AFFINITY_API_KEY")
    if not api_key:
        raise ValueError("Set AFFINITY_API_KEY environment variable or modify this script")
    return api_key


# =============================================================================
# Example 1: Comprehensive Company Analysis
# =============================================================================


def analyze_portfolio_companies(client: Affinity) -> None:
    """
    Analyze all companies in a portfolio list with enriched data.

    Demonstrates:
    - Getting list entries with field selection
    - Using enriched data fields
    - Iterating with automatic pagination
    """
    print("\n=== Portfolio Company Analysis ===\n")

    # Get all opportunity lists (pipelines)
    for lst in client.lists.all():
        if lst.type != ListType.OPPORTUNITY:
            continue

        print(f"Analyzing list: {lst.name} ({lst.list_size} entries)")

        # Get list entries with enriched fields
        entries = client.lists.entries(lst.id)

        # Request specific field types for efficiency
        for entry in entries.all(field_types=[FieldType.ENRICHED, FieldType.LIST]):
            if hasattr(entry.entity, "name"):
                company_name = entry.entity.name
                enriched_data = entry.fields

                print(f"  - {company_name}")

                # Access enriched fields (e.g., industry, employee count)
                if enriched_data:
                    for field_name, value in enriched_data.items():
                        if value:  # Only print non-empty values
                            print(f"      {field_name}: {value}")


# =============================================================================
# Example 2: Deal Pipeline Dashboard
# =============================================================================


def generate_pipeline_dashboard(client: Affinity, list_id: ListId) -> dict:
    """
    Generate a dashboard view of a deal pipeline.

    Demonstrates:
    - Getting fields for a list
    - Filtering entries
    - Aggregating data
    """
    print("\n=== Pipeline Dashboard ===\n")

    # Get list metadata
    pipeline = client.lists.get(list_id)
    print(f"Pipeline: {pipeline.name}")
    print(f"Total entries: {pipeline.list_size}")

    # Get field definitions for this list
    fields = client.lists.get_fields(list_id)

    # Find the status/stage field (typically a dropdown)
    stage_field = None
    for field in fields:
        if field.value_type == FieldValueType.DROPDOWN:
            if "stage" in field.name.lower() or "status" in field.name.lower():
                stage_field = field
                break

    if stage_field:
        print(f"\nStages available: {[opt.text for opt in stage_field.dropdown_options]}")

    # Aggregate entries by stage
    entries_service = client.lists.entries(list_id)
    stage_counts: dict[str, int] = {}
    total_count = 0

    for entry in entries_service.all():
        total_count += 1
        stage = entry.fields.get("Stage", "Unknown")
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    print("\nEntries by stage:")
    for stage, count in sorted(stage_counts.items()):
        percentage = (count / total_count * 100) if total_count > 0 else 0
        print(f"  {stage}: {count} ({percentage:.1f}%)")

    return {"total": total_count, "by_stage": stage_counts}


# =============================================================================
# Example 3: Contact Relationship Mapping
# =============================================================================


def map_contact_relationships(
    client: Affinity,
    company_id: CompanyId,
) -> dict:
    """
    Map all contacts and their relationships for a company.

    Demonstrates:
    - Getting company details with list entries
    - Getting person data
    - Building relationship graphs
    """
    print("\n=== Contact Relationship Mapping ===\n")

    # Get company with list entries
    company = client.companies.get(company_id)
    print(f"Company: {company.name}")
    print(f"Domain: {company.domain}")

    # Get all associated persons
    contacts = []
    for person_id in company.person_ids:
        try:
            person = client.persons.get(
                person_id,
                field_types=[FieldType.GLOBAL, FieldType.RELATIONSHIP_INTELLIGENCE],
            )
            contacts.append(person)
        except NotFoundError:
            print(f"  Warning: Person {person_id} not found")
            continue

    # Categorize contacts
    internal = [c for c in contacts if c.type == PersonType.INTERNAL]
    external = [c for c in contacts if c.type == PersonType.EXTERNAL]

    print(f"\nInternal contacts ({len(internal)}):")
    for person in internal:
        print(f"  - {person.full_name} ({person.primary_email})")

    print(f"\nExternal contacts ({len(external)}):")
    for person in external:
        print(f"  - {person.full_name} ({person.primary_email})")

    return {
        "company": company.name,
        "internal_contacts": len(internal),
        "external_contacts": len(external),
        "total_contacts": len(contacts),
    }


# =============================================================================
# Example 4: Batch Field Updates
# =============================================================================


def batch_update_deal_stages(
    client: Affinity,
    list_id: ListId,
    updates: dict[int, str],  # entry_id -> new_stage
) -> dict:
    """
    Batch update deal stages for multiple entries.

    Demonstrates:
    - Batch field updates
    - Error handling for partial failures
    - Rate limit awareness
    """
    print("\n=== Batch Deal Stage Updates ===\n")

    entries_service = client.lists.entries(list_id)

    # First, find the stage field
    fields = client.lists.get_fields(list_id)
    stage_field = None
    for field in fields:
        if "stage" in field.name.lower():
            stage_field = field
            break

    if not stage_field:
        print("Error: No stage field found on this list")
        return {"success": 0, "failed": len(updates)}

    results = {"success": 0, "failed": 0, "errors": []}

    for entry_id, new_stage in updates.items():
        try:
            entries_service.update_field_value(
                entry_id,
                FieldId(stage_field.id) if isinstance(stage_field.id, int) else stage_field.id,
                new_stage,
            )
            results["success"] += 1
            print(f"  Updated entry {entry_id} to stage '{new_stage}'")

        except RateLimitError as e:
            print(f"  Rate limited! Waiting {e.retry_after}s...")
            # In production, you'd wait and retry
            results["failed"] += 1
            results["errors"].append(f"Rate limited on entry {entry_id}")

        except ValidationError as e:
            results["failed"] += 1
            results["errors"].append(f"Validation error on entry {entry_id}: {e}")

        except AffinityError as e:
            results["failed"] += 1
            results["errors"].append(f"Error on entry {entry_id}: {e}")

    print(f"\nBatch update complete: {results['success']} succeeded, {results['failed']} failed")
    return results


# =============================================================================
# Example 5: Activity Tracking with Notes and Reminders
# =============================================================================


def setup_follow_up_workflow(
    client: Affinity,
    person_id: PersonId,
    meeting_notes: str,
    follow_up_days: int = 7,
) -> dict:
    """
    Create meeting notes and set a follow-up reminder.

    Demonstrates:
    - Creating notes
    - Creating reminders
    - Getting current user info
    """
    print("\n=== Follow-up Workflow Setup ===\n")

    # Get current user
    whoami = client.auth.whoami()
    current_user_id = UserId(whoami.user.id)
    print(f"Acting as: {whoami.user.first_name} {whoami.user.last_name}")

    # Get person details
    person = client.persons.get(person_id)
    print(f"Contact: {person.full_name}")

    # Create meeting note
    note = client.notes.create(
        NoteCreate(
            content=f"<p><strong>Meeting Notes - {datetime.now().strftime('%Y-%m-%d')}</strong></p><p>{meeting_notes}</p>",
            type=NoteType.HTML,
            person_ids=[person_id],
        )
    )
    print(f"Created note: {note.id}")

    # Create follow-up reminder
    due_date = datetime.now() + timedelta(days=follow_up_days)
    reminder = client.reminders.create(
        ReminderCreate(
            owner_id=current_user_id,
            type=ReminderType.ONE_TIME,
            content=f"Follow up with {person.full_name}",
            due_date=due_date,
            person_id=person_id,
        )
    )
    print(f"Created reminder for {due_date.strftime('%Y-%m-%d')}: {reminder.id}")

    return {
        "note_id": note.id,
        "reminder_id": reminder.id,
        "follow_up_date": due_date.isoformat(),
    }


# =============================================================================
# Example 6: Data Export and Reporting
# =============================================================================


def export_list_to_dict(client: Affinity, list_id: ListId) -> list[dict]:
    """
    Export all list entries to a list of dictionaries.

    Demonstrates:
    - Efficient pagination
    - Field selection
    - Data transformation
    """
    print("\n=== Data Export ===\n")

    lst = client.lists.get(list_id)
    print(f"Exporting: {lst.name} ({lst.list_size} entries)")

    # Get field definitions
    fields = client.lists.get_fields(list_id)
    field_names = {str(f.id): f.name for f in fields}

    exported_data = []
    entries_service = client.lists.entries(list_id)

    for entry in entries_service.all():
        record = {
            "entry_id": entry.id,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "entity_type": entry.type,
        }

        # Add entity data
        if hasattr(entry.entity, "name"):
            record["entity_name"] = entry.entity.name
        if hasattr(entry.entity, "domain"):
            record["entity_domain"] = entry.entity.domain
        if hasattr(entry.entity, "primary_email"):
            record["entity_email"] = entry.entity.primary_email

        # Add field values with human-readable names
        for field_id, value in entry.fields.items():
            field_name = field_names.get(str(field_id), field_id)
            record[field_name] = value

        exported_data.append(record)

    print(f"Exported {len(exported_data)} records")
    return exported_data


# =============================================================================
# Example 7: Rate Limit Monitoring
# =============================================================================


def monitor_rate_limits(client: Affinity) -> dict:
    """
    Monitor current rate limit status.

    Demonstrates:
    - Checking rate limits via API
    - Accessing local rate limit tracking
    """
    print("\n=== Rate Limit Status ===\n")

    # Get rate limits from API (most accurate)
    try:
        api_limits = client.auth.get_rate_limits()
        print("From API:")
        print(
            f"  Per minute: {api_limits.api_key_per_minute.remaining}/{api_limits.api_key_per_minute.per}"
        )
        print(
            f"  Per month: {api_limits.api_key_per_month.remaining}/{api_limits.api_key_per_month.per}"
        )
    except AffinityError:
        print("Could not fetch API rate limits")
        api_limits = None

    # Get locally tracked limits (updated from response headers)
    local_state = client.rate_limit_state
    print("\nLocal tracking:")
    print(f"  User remaining: {local_state['user_remaining']}/{local_state['user_limit']}")
    print(f"  Org remaining: {local_state['org_remaining']}/{local_state['org_limit']}")
    print(f"  User reset in: {local_state['user_reset_seconds']}s")

    return {
        "api_limits": api_limits,
        "local_state": local_state,
    }


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run example demonstrations."""
    print("=" * 60)
    print("Affinity SDK - Advanced Usage Examples")
    print("=" * 60)

    # Initialize client
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"\nError: {e}")
        print("\nTo run these examples:")
        print("  export AFFINITY_API_KEY='your-api-key'")
        print("  python advanced_usage.py")
        return

    with Affinity(api_key=api_key) as client:
        # Run examples - uncomment the ones you want to try

        # Example 1: Analyze portfolio
        # analyze_portfolio_companies(client)

        # Example 2: Pipeline dashboard (requires a list ID)
        # generate_pipeline_dashboard(client, ListId(YOUR_LIST_ID))

        # Example 3: Contact mapping (requires a company ID)
        # map_contact_relationships(client, CompanyId(YOUR_COMPANY_ID))

        # Example 4: Batch updates (requires list ID and entry IDs)
        # batch_update_deal_stages(client, ListId(YOUR_LIST_ID), {
        #     ENTRY_ID_1: "Qualified",
        #     ENTRY_ID_2: "Proposal",
        # })

        # Example 5: Follow-up workflow (requires person ID)
        # setup_follow_up_workflow(
        #     client,
        #     PersonId(YOUR_PERSON_ID),
        #     "Great meeting! Discussed partnership opportunities.",
        # )

        # Example 6: Data export (requires list ID)
        # data = export_list_to_dict(client, ListId(YOUR_LIST_ID))

        # Example 7: Rate limit monitoring (always works)
        monitor_rate_limits(client)

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
