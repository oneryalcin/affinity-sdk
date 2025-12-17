# Affinity Python SDK

[![CI](https://github.com/yaniv-golan/affinity-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/yaniv-golan/affinity-sdk/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/yaniv-golan/affinity-sdk/branch/main/graph/badge.svg)](https://codecov.io/gh/yaniv-golan/affinity-sdk)
[![PyPI version](https://img.shields.io/pypi/v/affinity-sdk.svg)](https://pypi.org/project/affinity-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/affinity-sdk.svg)](https://pypi.org/project/affinity-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Typed](https://img.shields.io/badge/typed-mypy-blue.svg)](https://mypy-lang.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-orange.svg)](https://docs.pydantic.dev/)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://yaniv-golan.github.io/affinity-sdk/)

A modern, strongly-typed Python wrapper for the [Affinity CRM API](https://api-docs.affinity.co/).

Disclaimer: This is an unofficial community project and is not affiliated with, endorsed by, or sponsored by Affinity. “Affinity” and related marks are trademarks of their respective owners. Use of the Affinity API is subject to Affinity’s Terms of Service.

Maintainer: GitHub: `yaniv-golan`

Documentation: https://yaniv-golan.github.io/affinity-sdk/

## Features

- **V2 terminology** - Uses `Company` (not `Organization`) throughout for consistency with Affinity's latest API
- **Strong typing** - Full Pydantic V2 models with typed ID classes (`PersonId`, `CompanyId`, `ListId`, etc.)
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

Optional (local dev): load `.env` automatically:

```bash
pip install "affinity-sdk[dotenv]"
```

## Quick Start

```python
from affinity import Affinity
from affinity.types import FieldType, PersonId

# Recommended: read the API key from the environment (AFFINITY_API_KEY)
client = Affinity.from_env()

# If you use a local `.env` file (requires `affinity-sdk[dotenv]`)
# client = Affinity.from_env(load_dotenv=True)

# Or pass it explicitly
# client = Affinity(api_key="your-api-key")

# Or use as a context manager
with Affinity.from_env() as client:
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
from affinity import Affinity, F
from affinity.models import CompanyCreate
from affinity.types import CompanyId, FieldType

with Affinity(api_key="your-key") as client:
    # List companies with filtering (V2 API)
    companies = client.companies.list(
        filter=F.field("domain").contains("acme"),
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
from affinity.models import PersonCreate
from affinity.types import PersonType

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
from affinity.models import ListCreate
from affinity.types import CompanyId, FieldId, FieldType, ListId, ListType

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
    entries = client.lists.entries(ListId(123))

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
from affinity.models import NoteCreate, NoteUpdate
from affinity.types import NoteType, PersonId

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
    for note_item in result.data:
        print(note_item.content)

    # Update a note
    client.notes.update(note.id, NoteUpdate(content="Updated content"))

    # Delete a note
    client.notes.delete(note.id)
```

### Reminders

```python
from datetime import datetime, timedelta
from affinity import Affinity
from affinity.models import ReminderCreate
from affinity.types import PersonId, ReminderResetType, ReminderType, UserId

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

### Files

```python
from affinity import Affinity
from affinity.types import FileId, PersonId

with Affinity(api_key="your-key") as client:
    # Download into memory (bytes)
    content = client.files.download(FileId(123))

    # Stream download (for progress bars / piping / large files)
    for chunk in client.files.download_stream(FileId(123), chunk_size=64_000):
        ...

    # Download to disk
    saved_path = client.files.download_to(FileId(123), "report.pdf", overwrite=False)

    # Upload (multipart form data)
    client.files.upload(
        files={"file": ("report.pdf", b"hello", "application/pdf")},
        person_id=PersonId(123),
    )

    # Upload from disk / bytes (ergonomic helpers)
    client.files.upload_path("report.pdf", person_id=PersonId(123))
    client.files.upload_bytes(b"hello", "report.txt", person_id=PersonId(123))

    # Iterate all files attached to an entity
    for f in client.files.all(person_id=PersonId(123)):
        print(f.name, f.size)
```

### Webhooks

```python
from affinity import Affinity
from affinity.models import WebhookCreate, WebhookUpdate
from affinity.types import WebhookEvent

with Affinity(api_key="your-key") as client:
    # Create a webhook subscription
    webhook = client.webhooks.create(
        WebhookCreate(
            webhook_url="https://your-server.com/webhook",
            subscriptions=[
                WebhookEvent.LIST_ENTRY_CREATED,
                WebhookEvent.LIST_ENTRY_DELETED,
                WebhookEvent.FIELD_VALUE_UPDATED,
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

The SDK uses strongly-typed ID classes (int/str subclasses) to prevent accidental mixing:

```python
from affinity.types import PersonId, CompanyId, ListId

# These are different types - IDE and type checker will catch mixing
person_id = PersonId(123)
company_id = CompanyId(456)

# This would be a type error:
# client.persons.get(company_id)  # Wrong type!
```

All magic numbers are replaced with enums:

```python
from affinity.types import (
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

    # Hooks (DX-008)
    # on_request=lambda req: print(req.method, req.url),
    # on_response=lambda resp: print(resp.status_code, resp.request.url),
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

Async support currently covers core read flows (`companies`, `persons`, `lists`, `opportunities`) plus `tasks`. V1-only services (notes, reminders, webhooks, etc.) are sync-only.

If you don't use `async with`, make sure to `await client.close()` (e.g., in a `finally`) to avoid leaking connections.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Optional: live API smoke tests (requires a real API key)
AFFINITY_API_KEY="..." pytest -m integration -q

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
