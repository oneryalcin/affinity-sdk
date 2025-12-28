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

## Memory considerations

For very large datasets (thousands of pages), prefer `iter()` or `all()` over manually calling `page.next_page()` in a loop. The iterator pattern processes items one at a time without accumulating page objects in memory.

If you need to hold `Page` objects (e.g., for batch processing), process and release them promptly to allow garbage collection.

## Next steps

- [Filtering](filtering.md)
- [Field types & values](field-types-and-values.md)
- [Examples](../examples.md)
- [API reference](../reference/services/companies.md)
