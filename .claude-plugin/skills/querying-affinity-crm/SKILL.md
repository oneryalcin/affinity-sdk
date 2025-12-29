---
name: querying-affinity-crm
description: Queries and manages Affinity CRM data using the Python SDK (affinity package) or xaffinity CLI. Use when looking up people, contacts, companies, organizations, deals, opportunities, lists, or pipelines in Affinity. Handles person search, company lookup, list entries, field values, and data export.
---

# Querying Affinity CRM

The Affinity Python SDK (`affinity` package) and CLI (`xaffinity`) provide access to Affinity CRM data.

## Critical Patterns (Must Follow)

### Read-Only by Default - IMPORTANT

**Always use read-only mode unless the user explicitly requests data modification.**

CRM data is sensitive. Scripts should default to read-only to prevent accidental changes.

**SDK - Use read-only policy:**
```python
from affinity import Affinity
from affinity.policies import Policies, WritePolicy

# Default for scripts - prevents accidental writes
with Affinity.from_env(policies=Policies(write=WritePolicy.DENY)) as client:
    ...  # Write operations will raise WriteNotAllowedError
```

**CLI - Use --readonly flag (and --dotenv to load API key from .env):**
```bash
xaffinity --dotenv --readonly person ls --all
xaffinity --dotenv --readonly company get 123
```

Only remove the read-only restriction when the user explicitly confirms they want to create, update, or delete data.

### Typed IDs (SDK) - Required

```python
from affinity.types import PersonId, CompanyId, ListId, OpportunityId

client.persons.get(PersonId(123))      # Correct
client.companies.get(CompanyId(456))   # Correct
client.persons.get(123)                # WRONG - will fail type checking
```

Available typed IDs: `PersonId`, `CompanyId`, `ListId`, `ListEntryId`, `OpportunityId`, `FieldId`, `NoteId`, `UserId`

### Client Lifecycle (SDK) - Always Use Context Manager

```python
from affinity import Affinity

with Affinity.from_env() as client:  # Reads AFFINITY_API_KEY from environment
    ...

# Or with explicit key:
with Affinity(api_key="your-key") as client:
    ...
```

### Filtering Limitation - Custom Fields Only

The `F` filter builder and `--filter` CLI option work **only on custom fields**, not built-in properties.

**Works (custom fields):**
```python
from affinity import F
client.persons.list(filter=F.field("Department").equals("Sales"))
```

**Does NOT work (built-in properties):**
- `type`, `firstName`, `lastName`, `primaryEmail` (Person)
- `name`, `domain`, `domains` (Company)
- `name`, `listId` (Opportunity)

Filter built-in properties client-side after fetching data.

## SDK Quick Reference

```python
from affinity import Affinity, F, AsyncAffinity
from affinity.types import PersonId, CompanyId, ListId, FieldType
from affinity.exceptions import NotFoundError, RateLimitError

with Affinity.from_env() as client:
    # Identity
    me = client.whoami()

    # Pagination - choose based on data size
    page = client.companies.list(limit=50)           # Single page
    all_companies = client.companies.all()           # All pages (list, max 100k default)
    for person in client.persons.iter():             # Memory-efficient iterator
        ...

    # Field selection
    client.companies.list(field_types=[FieldType.ENRICHED, FieldType.GLOBAL])

    # Filtering (custom fields only)
    client.persons.list(filter=F.field("Department").equals("Sales"))
    client.companies.list(filter=F.field("Industry").contains("Tech"))

    # Complex filters
    client.persons.list(
        filter=F.field("Status").equals("Active") & F.field("Region").equals("US")
    )

    # Lists and entries
    for lst in client.lists.all():
        entries_service = client.lists.entries(lst.id)
        for entry in entries_service.all():
            ...

    # Resolve by name
    pipeline = client.lists.resolve(name="Deal Pipeline")

# Async variant
async with AsyncAffinity.from_env() as client:
    companies = await client.companies.all()
```

See [SDK_REFERENCE.md](SDK_REFERENCE.md) for complete patterns including error handling, rate limits, and field values.

## CLI Quick Reference

```bash
# Authentication (set environment variable)
export AFFINITY_API_KEY="your-key"

# Identity
xaffinity whoami

# List entities
xaffinity person ls --all
xaffinity company ls --all
xaffinity opportunity ls --all

# Get by ID
xaffinity person get 123
xaffinity company get 456 --all-fields

# Export to CSV
xaffinity person ls --all --csv people.csv
xaffinity company ls --all --csv companies.csv --csv-bom  # Excel-compatible
xaffinity list export 12345 --all --csv entries.csv

# JSON output for scripting
xaffinity person ls --json --all | jq '.data.persons[]'

# Filter on custom fields
xaffinity person ls --filter 'field("Department") = "Sales"' --all

# Filter built-in properties (client-side via jq)
xaffinity person ls --json --all | jq '.data.persons[] | select(.type == "internal")'

# Resolve by name or URL
xaffinity person get email:alice@example.com
xaffinity company get domain:acme.com
xaffinity resolve-url "https://app.affinity.co/companies/123"
```

See [CLI_REFERENCE.md](CLI_REFERENCE.md) for complete command reference.

## Common Workflows

### Export all contacts to CSV
```bash
xaffinity person ls --all --csv contacts.csv --csv-bom
```

### Get list entries with custom fields
```python
with Affinity.from_env() as client:
    pipeline = client.lists.resolve(name="Deal Pipeline")
    entries = client.lists.entries(pipeline.id)
    for entry in entries.all(field_types=[FieldType.LIST]):
        print(entry.entity.name, entry.fields.data)
```

### Find person by email
```python
with Affinity.from_env() as client:
    results = client.persons.search("alice@example.com")
    if results.data:
        person = results.data[0]
```

Or via CLI:
```bash
xaffinity person get email:alice@example.com
```
