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
