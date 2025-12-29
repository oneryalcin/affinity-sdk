# SDK Reference

Complete patterns for the Affinity Python SDK (`affinity` package).

## Installation

```bash
pip install affinity-sdk

# With .env file support
pip install "affinity-sdk[dotenv]"
```

## Client Initialization

```python
from affinity import Affinity, AsyncAffinity

# From environment variable (AFFINITY_API_KEY)
with Affinity.from_env() as client:
    ...

# With .env file loading (requires dotenv extra)
with Affinity.from_env(load_dotenv=True) as client:
    ...

# Explicit API key
with Affinity(api_key="your-key") as client:
    ...

# Read-only mode (prevents accidental writes)
from affinity.policies import Policies, WritePolicy
client = Affinity.from_env(policies=Policies(write=WritePolicy.DENY))

# Async client
async with AsyncAffinity.from_env() as client:
    companies = await client.companies.all()
```

## Typed IDs

Always use typed IDs to prevent mixing up entity types:

```python
from affinity.types import (
    PersonId, CompanyId, ListId, ListEntryId,
    OpportunityId, FieldId, NoteId, UserId
)

person = client.persons.get(PersonId(123))
company = client.companies.get(CompanyId(456))
entries = client.lists.entries(ListId(789))
```

## Pagination

```python
# Single page (default 100 items)
page = client.companies.list(limit=50)
for company in page.data:
    ...
if page.pagination.next_url:
    next_page = page.get_url(page.pagination.next_url)

# All pages as list (default max 100,000 items)
all_companies = client.companies.all()

# Adjust or disable limit
companies = client.companies.all(max_results=1000)
companies = client.companies.all(max_results=None)  # No limit (use with caution)

# Memory-efficient iterator (for large datasets)
for person in client.persons.iter():
    process(person)

# Page-by-page iteration
for page in client.companies.pages():
    for company in page.data:
        ...

# Progress callback
from affinity import PaginationProgress

def log_progress(p: PaginationProgress) -> None:
    print(f"Page {p.page_number}: {p.items_so_far} items")

for company in client.companies.all(on_progress=log_progress):
    ...
```

## Filtering (Custom Fields Only)

```python
from affinity import F

# Simple comparisons
client.persons.list(filter=F.field("Department").equals("Sales"))
client.companies.list(filter=F.field("Industry").contains("Tech"))
client.persons.list(filter=F.field("Title").starts_with("VP"))
client.opportunities.list(filter=F.field("Amount").greater_than(100000))

# Null checks
client.persons.list(filter=F.field("Manager").is_null())
client.persons.list(filter=F.field("Email").is_not_null())

# Boolean logic
active_sales = client.persons.list(
    filter=F.field("Department").equals("Sales") & F.field("Status").equals("Active")
)

tech_or_finance = client.companies.list(
    filter=F.field("Industry").equals("Technology") | F.field("Industry").equals("Finance")
)

non_archived = client.persons.list(
    filter=~F.field("Archived").equals(True)
)

# In list
multi_region = client.companies.list(
    filter=F.field("Region").in_list(["US", "Canada", "Mexico"])
)
```

**Cannot filter**: `type`, `firstName`, `lastName`, `primaryEmail`, `name`, `domain` (fetch all, filter client-side).

## Field Selection

```python
from affinity.types import FieldType

# Request specific field types
client.companies.list(field_types=[FieldType.ENRICHED])
client.persons.get(PersonId(123), field_types=[FieldType.GLOBAL, FieldType.RELATIONSHIP_INTELLIGENCE])

# Check if fields were requested
if company.fields.requested:
    for field_name, value in company.fields.data.items():
        print(f"{field_name}: {value}")
```

Available field types: `GLOBAL`, `LIST`, `ENRICHED`, `RELATIONSHIP_INTELLIGENCE`

## Services

```python
with Affinity.from_env() as client:
    # Core entities
    client.persons.list() / .get() / .all() / .search()
    client.companies.list() / .get() / .all() / .search()
    client.opportunities.list() / .get() / .all()

    # Lists
    client.lists.list() / .get() / .all()
    client.lists.resolve(name="Pipeline Name")
    client.lists.get_fields(ListId(123))

    # List entries
    entries_service = client.lists.entries(ListId(123))
    entries_service.list() / .get() / .all()
    entries_service.create(...)
    entries_service.update_field_value(entry_id, field_id, value)

    # Notes, reminders, interactions
    client.notes.list() / .create()
    client.reminders.list() / .create()
    client.interactions.list()

    # Rate limits
    snapshot = client.rate_limits.snapshot()
    refreshed = client.rate_limits.refresh()

    # Identity
    me = client.whoami()
```

## Error Handling

```python
from affinity.exceptions import (
    AffinityError,           # Base class
    AuthenticationError,     # 401 - invalid/missing API key
    AuthorizationError,      # 403 - insufficient permissions
    NotFoundError,           # 404 - entity not found
    ValidationError,         # 400/422 - invalid parameters
    RateLimitError,          # 429 - rate limited
    ServerError,             # 500/503 - server errors
    WriteNotAllowedError,    # Write attempted in read-only mode
    TooManyResultsError,     # .all() exceeded max_results
)

try:
    person = client.persons.get(PersonId(123))
except NotFoundError:
    print("Person not found")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}")
except AffinityError as e:
    print(f"Error: {e}")
    if e.diagnostics:
        print(f"Request ID: {e.diagnostics.request_id}")
```

## Rate Limits

```python
# Check current status (from cached headers)
snapshot = client.rate_limits.snapshot()
print(f"Per-minute: {snapshot.api_key_per_minute.remaining}/{snapshot.api_key_per_minute.limit}")
print(f"Monthly: {snapshot.org_monthly.remaining}/{snapshot.org_monthly.limit}")

# Refresh from API
refreshed = client.rate_limits.refresh()
```

## Creating and Updating

```python
from affinity.models import NoteCreate, ReminderCreate
from affinity.types import NoteType, ReminderType

# Create note
note = client.notes.create(NoteCreate(
    content="<p>Meeting notes</p>",
    type=NoteType.HTML,
    person_ids=[PersonId(123)],
))

# Create reminder
from datetime import datetime, timedelta
reminder = client.reminders.create(ReminderCreate(
    owner_id=UserId(me.user.id),
    type=ReminderType.ONE_TIME,
    content="Follow up",
    due_date=datetime.now() + timedelta(days=7),
    person_id=PersonId(123),
))

# Update field value
entries_service = client.lists.entries(ListId(123))
entries_service.update_field_value(
    ListEntryId(456),
    FieldId(789),
    "New Value"
)
```

## Retry Behavior

- **GET/HEAD**: Automatic retries (3 by default) for rate limits and transient errors
- **POST/PUT/PATCH/DELETE**: No automatic retries (to avoid duplicates)

Configure retries:
```python
client = Affinity(api_key="key", max_retries=5)
```
