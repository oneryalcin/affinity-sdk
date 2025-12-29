# Pagination

Most list endpoints support both:

- `list(...)`: fetch a single page
- `all(...)` / `iter(...)`: iterate across pages automatically

Example:

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    for company in client.companies.all():
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

## Next steps

- [Filtering](filtering.md)
- [Field types & values](field-types-and-values.md)
- [Examples](../examples.md)
- [API reference](../reference/services/companies.md)
