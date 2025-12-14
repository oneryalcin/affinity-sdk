# Affinity Python SDK

A modern, strongly-typed Python wrapper for the [Affinity CRM API](https://api-docs.affinity.co/).

Maintainer: GitHub: `yaniv-golan`

## Features

- **V2 terminology** - Uses `Company` (not `Organization`) throughout for consistency with Affinity's latest API
- **Strong typing** - Full Pydantic V2 models with `NewType` IDs (`PersonId`, `CompanyId`, `ListId`, etc.)
- **No magic numbers** - Comprehensive enums for all API constants
- **Automatic pagination** - Iterator support for seamless pagination
- **Smart API routing** - Uses V2 API for reads, V1 for writes (V2 doesn't support all operations yet)
- **Rate limit handling** - Automatic retry with exponential backoff
- **Response caching** - Optional caching for field metadata
- **Both sync and async** - Full support for both patterns

## Installation

```bash
pip install affinity-sdk
```

Requires Python 3.10+.

## Quick Start

```python
from affinity import Affinity
from affinity.models import PersonId, CompanyId, ListId, FieldType

# Initialize the client
client = Affinity(api_key="your-api-key")

# Or use as a context manager
with Affinity(api_key="your-api-key") as client:
    # List all companies
    for company in client.companies.all():
        print(f"{company.name} ({company.domain})")
    
    # Get a person with enriched data
    person = client.persons.get(
        PersonId(12345),
        field_types=[FieldType.ENRICHED, FieldType.GLOBAL]
    )
    print(f"{person.first_name} {person.last_name}: {person.primary_email}")
```

## Usage Examples

### Working with Companies

```python
from affinity import Affinity
from affinity.models import CompanyId, CompanyCreate, FieldType

with Affinity(api_key="your-key") as client:
    # List companies with filtering (V2 API)
    companies = client.companies.list(
        filter='domain =~ "acme"',
        field_types=[FieldType.ENRICHED],
    )
    
    # Iterate through all companies with automatic pagination
    for company in client.companies.all():
        print(f"{company.name}: {company.fields}")
    
    # Get a specific company
    company = client.companies.get(CompanyId(123))
    
    # Create a company (uses V1 API)
    new_company = client.companies.create(
        CompanyCreate(
            name="Acme Corp",
            domain="acme.com",
        )
    )
    
    # Search by name, domain, or email
    results = client.companies.search("acme.com")
    
    # Get list entries for a company
    entries = client.companies.get_list_entries(CompanyId(123))
```

### Working with Persons

```python
from affinity import Affinity
from affinity.models import PersonId, PersonCreate, PersonType

with Affinity(api_key="your-key") as client:
    # Get all internal team members
    for person in client.persons.all():
        if person.type == PersonType.INTERNAL:
            print(f"{person.first_name} {person.last_name}")
    
    # Create a contact
    person = client.persons.create(
        PersonCreate(
            first_name="Jane",
            last_name="Doe",
            emails=["jane@example.com"],
        )
    )
    
    # Search by email
    results = client.persons.search("jane@example.com")
```

### Working with Lists

```python
from affinity import Affinity
from affinity.models import (
    ListId, ListEntryId, FieldId, CompanyId,
    ListCreate, ListType, FieldType,
)

with Affinity(api_key="your-key") as client:
    # Get all lists
    for lst in client.lists.all():
        print(f"{lst.name} ({lst.type.name})")
    
    # Get a specific list with field metadata
    pipeline = client.lists.get(ListId(123))
    print(f"Fields: {[f.name for f in pipeline.fields]}")
    
    # Create a new list
    new_list = client.lists.create(
        ListCreate(
            name="Q1 Pipeline",
            type=ListType.OPPORTUNITY,
            is_public=True,
        )
    )
    
    # Work with list entries
    entries = client.entries(ListId(123))
    
    # List entries with field data
    for entry in entries.all(field_types=[FieldType.LIST_SPECIFIC]):
        print(f"{entry.entity.name}: {entry.fields}")
    
    # Add a company to the list
    entry = entries.add_company(CompanyId(456))
    
    # Update field values
    entries.update_field_value(
        entry.id,
        FieldId(101),
        "In Progress"
    )
    
    # Batch update multiple fields
    entries.batch_update_fields(
        entry.id,
        {
            FieldId(101): "Closed Won",
            FieldId(102): 100000,
            FieldId(103): "2024-03-15",
        }
    )
    
    # Use saved views
    views = client.lists.get_saved_views(ListId(123))
    for view in views.data:
        results = entries.from_saved_view(view.id)
```

### Notes

```python
from affinity import Affinity
from affinity.models import PersonId, NoteCreate, NoteType

with Affinity(api_key="your-key") as client:
    # Create a note
    note = client.notes.create(
        NoteCreate(
            content="<p>Great meeting!</p>",
            type=NoteType.HTML,
            person_ids=[PersonId(123)],
        )
    )
    
    # Get notes for a person
    result = client.notes.list(person_id=PersonId(123))
    for note in result["notes"]:
        print(note["content"])
    
    # Update a note
    client.notes.update(note.id, NoteUpdate(content="Updated content"))
    
    # Delete a note
    client.notes.delete(note.id)
```

### Reminders

```python
from datetime import datetime, timedelta
from affinity import Affinity
from affinity.models import (
    PersonId, UserId,
    ReminderCreate, ReminderType, ReminderResetType,
)

with Affinity(api_key="your-key") as client:
    # Get current user
    me = client.auth.whoami()
    
    # Create a follow-up reminder
    reminder = client.reminders.create(
        ReminderCreate(
            owner_id=UserId(me.user.id),
            type=ReminderType.ONE_TIME,
            content="Follow up on proposal",
            due_date=datetime.now() + timedelta(days=7),
            person_id=PersonId(123),
        )
    )
    
    # Create a recurring reminder
    recurring = client.reminders.create(
        ReminderCreate(
            owner_id=UserId(me.user.id),
            type=ReminderType.RECURRING,
            reset_type=ReminderResetType.THIRTY_DAYS,
            content="Monthly check-in",
            person_id=PersonId(123),
        )
    )
```

### Webhooks

```python
from affinity import Affinity
from affinity.models import WebhookCreate, WebhookEventType

with Affinity(api_key="your-key") as client:
    # Create a webhook subscription
    webhook = client.webhooks.create(
        WebhookCreate(
            webhook_url="https://your-server.com/webhook",
            subscriptions=[
                WebhookEventType.LIST_ENTRY_CREATED,
                WebhookEventType.LIST_ENTRY_DELETED,
                WebhookEventType.FIELD_VALUE_UPDATED,
            ],
        )
    )
    
    # List all webhooks (max 3 per instance)
    webhooks = client.webhooks.list()
    
    # Disable a webhook
    client.webhooks.update(
        webhook.id,
        WebhookUpdate(disabled=True)
    )
```

### Rate Limits

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    # Get rate limit info from API
    limits = client.auth.get_rate_limits()
    print(f"API key per minute: {limits.api_key_per_minute.remaining}/{limits.api_key_per_minute.per}")
    print(f"API key per month: {limits.api_key_per_month.remaining}/{limits.api_key_per_month.per}")
    
    # Get locally tracked rate limit state
    state = client.rate_limit_state
    print(f"User remaining: {state['user_remaining']}")
    print(f"Org remaining: {state['org_remaining']}")
```

## Type System

The SDK uses Python's `NewType` to create distinct ID types that prevent accidental mixing:

```python
from affinity.models import PersonId, CompanyId, ListId

# These are different types - IDE and type checker will catch mixing
person_id = PersonId(123)
company_id = CompanyId(456)

# This would be a type error:
# client.persons.get(company_id)  # Wrong type!
```

All magic numbers are replaced with enums:

```python
from affinity.models import (
    ListType,        # PERSON, ORGANIZATION, OPPORTUNITY
    PersonType,      # INTERNAL, EXTERNAL, COLLABORATOR
    FieldValueType,  # TEXT, NUMBER, DATE, PERSON, etc.
    InteractionType, # EMAIL, MEETING, CALL, CHAT
    # ... and more
)
```

## API Coverage

| Feature | V2 | V1 | SDK |
|---------|:--:|:--:|:---:|
| Companies (read) | ✅ | ✅ | V2 |
| Companies (write) | ❌ | ✅ | V1 |
| Persons (read) | ✅ | ✅ | V2 |
| Persons (write) | ❌ | ✅ | V1 |
| Lists (read) | ✅ | ✅ | V2 |
| Lists (write) | ❌ | ✅ | V1 |
| List Entries (read) | ✅ | ✅ | V2 |
| List Entries (write) | ❌ | ✅ | V1 |
| Field Values (read) | ✅ | ✅ | V2 |
| Field Values (write) | ✅ | ✅ | V2 |
| Notes | Read-only | ✅ | V1 |
| Reminders | ❌ | ✅ | V1 |
| Webhooks | ❌ | ✅ | V1 |
| Interactions | Read-only | ✅ | V1 |
| Entity Files | ❌ | ✅ | V1 |
| Relationship Strengths | ❌ | ✅ | V1 |

## Configuration

```python
from affinity import Affinity

client = Affinity(
    api_key="your-api-key",
    
    # Timeouts and retries
    timeout=30.0,           # Request timeout (seconds)
    max_retries=3,          # Retries for rate-limited requests
    
    # Caching
    enable_cache=True,      # Cache field metadata
    cache_ttl=300.0,        # Cache TTL (seconds)
    
    # Debugging
    log_requests=False,     # Log all HTTP requests
)
```

## Error Handling

The SDK provides a comprehensive exception hierarchy:

```python
from affinity import (
    Affinity,
    AffinityError,
    AuthenticationError,
    RateLimitError,
    NotFoundError,
    ValidationError,
)

try:
    with Affinity(api_key="your-key") as client:
        person = client.persons.get(PersonId(99999999))
except AuthenticationError:
    print("Invalid API key")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except NotFoundError:
    print("Person not found")
except ValidationError as e:
    print(f"Invalid request: {e.message}")
except AffinityError as e:
    print(f"API error: {e}")
```

## Async Support

```python
import asyncio
from affinity import AsyncAffinity

async def main():
    async with AsyncAffinity(api_key="your-key") as client:
        # Async operations
        companies = await client.companies.list()
        async for company in client.companies.all():
            print(company.name)

asyncio.run(main())
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy affinity

# Linting
ruff check affinity
ruff format affinity
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read our contributing guidelines first.

## Links

- Repository: https://github.com/yaniv-golan/affinity-sdk
- Issues: https://github.com/yaniv-golan/affinity-sdk/issues
- [Affinity API V2 Documentation](https://api-docs.affinity.co/reference/getting-started-with-your-api)
- [Affinity API V1 Documentation](https://api-docs.affinity.co/reference)
