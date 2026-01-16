# Pagination

Most list endpoints support both:

- `list(...)`: fetch a single page
- `iter(...)` / `all(...)`: iterate across pages automatically

## Services with pagination

All paginated services support `iter()` for streaming and `all()` for collecting results:

| Service | Methods |
|---------|---------|
| `persons` | `iter()`, `all()`, `pages()` |
| `companies` | `iter()`, `all()`, `pages()` |
| `opportunities` | `iter()`, `all()`, `pages()` |
| `lists` | `iter()`, `all()`, `pages()` |
| `notes` | `iter()` |
| `reminders` | `iter()` |
| `interactions` | `iter()` |
| `files` | `iter()`, `all()` |

Example:

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    for company in client.companies.iter():
        print(company.name)
```

## Progress callbacks

Use `on_progress` to track pagination progress for logging, progress bars, or debugging:

```python
from affinity import Affinity, PaginationProgress

def log_progress(p: PaginationProgress) -> None:
    print(f"Page {p.page_number}: {p.items_so_far} items so far")

with Affinity(api_key="your-key") as client:
    for page in client.companies.pages(on_progress=log_progress):
        for company in page.data:
            process(company)
```

`PaginationProgress` provides:

| Field | Description |
|-------|-------------|
| `page_number` | 1-indexed page number |
| `items_in_page` | Items in current page |
| `items_so_far` | Cumulative items including current page |
| `has_next` | Whether more pages exist |

## Memory safety

The `.all()` method returns a list, which can cause out-of-memory issues with large datasets. By default, it limits results to 100,000 items and raises `TooManyResultsError` if exceeded:

```python
from affinity import Affinity, TooManyResultsError

with Affinity(api_key="your-key") as client:
    try:
        # Raises TooManyResultsError if > 100,000 items
        companies = client.companies.all()
    except TooManyResultsError as e:
        print(f"Too many results: {e.count} items")
```

Adjust or disable the limit with `max_results`:

```python
# Lower limit for safety
companies = client.companies.all(max_results=1000)

# Disable limit (use with caution)
companies = client.companies.all(max_results=None)
```

For very large datasets, prefer streaming with `iter()`:

```python
# Memory-efficient: processes one item at a time
for company in client.companies.iter():
    process(company)
```

## Manual pagination

When iterating pages manually, use the `next_cursor` property to get the cursor for the next page:

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    page = client.companies.list(limit=100)

    while page.has_next:
        process(page.data)
        # Always use next_cursor for the next page cursor
        page = client.companies.list(limit=100, cursor=page.next_cursor)
```

!!! tip "Use `next_cursor`, not `pagination.next_cursor`"
    Always use the `next_cursor` property on `PaginatedResponse`. This works consistently
    across all services regardless of the underlying API version.

## Next steps

- [Filtering](filtering.md)
- [Field types & values](field-types-and-values.md)
- [Examples](../examples.md)
- [API reference](../reference/services/companies.md)
