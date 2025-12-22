# Examples

All examples assume `AFFINITY_API_KEY` is set:

```bash
export AFFINITY_API_KEY="your-api-key"
```

Run an example with:

```bash
python examples/basic_usage.py
```

## Basic

- [`examples/basic_usage.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/basic_usage.py) — small end-to-end tour of core services
- [`examples/advanced_usage.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/advanced_usage.py) — deeper patterns and best practices

## Async

- [`examples/async_lifecycle.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/async_lifecycle.py) — async client lifecycle and usage

## Filtering and hooks

- [`examples/filter_builder.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/filter_builder.py) — build V2 filter expressions with `affinity.F`
- [`examples/hooks_debugging.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/hooks_debugging.py) — request/response hooks for debugging

## Lists, resolve helpers, tasks

- [`examples/list_management.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/list_management.py) — list CRUD and entry operations
- [`examples/resolve_helpers.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/resolve_helpers.py) — resolve helpers (IDs from external identifiers)
- [`examples/task_polling.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/task_polling.py) — polling long-running tasks

## Field Value Changes (audit history)

Query the change history for a specific field on an entity:

```python
from affinity import Affinity
from affinity.types import CompanyId, FieldId, FieldValueChangeAction

client = Affinity.from_env()

# Get all changes to field "field-123" for company 456
changes = client.field_value_changes.list(
    FieldId("field-123"),
    company_id=CompanyId(456),
)

for change in changes:
    print(f"{change.changed_at}: {change.value} (action={change.action_type})")

# Filter by action type (e.g., only updates)
updates = client.field_value_changes.list(
    FieldId("field-123"),
    company_id=CompanyId(456),
    action_type=FieldValueChangeAction.UPDATE,
)
```

Note: This endpoint is not paginated. For large histories, use narrow filters.

## V1-only exception: company -> people associations

V2 does not expose a company -> people association endpoint yet. These helpers use the v1
organizations API and are documented as exceptions:

```python
from affinity import Affinity
from affinity.types import CompanyId

client = Affinity.from_env()

person_ids = client.companies.get_associated_person_ids(CompanyId(224925494))
people = client.companies.get_associated_people(CompanyId(224925494), max_results=5)
```
