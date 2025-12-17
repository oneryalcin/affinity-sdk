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

## Next steps

- [Filtering](filtering.md)
- [Field types & values](field-types-and-values.md)
- [Examples](../examples.md)
- [API reference](../reference/services/companies.md)
