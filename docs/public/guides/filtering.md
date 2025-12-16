# Filtering

For V2 list endpoints that accept `filter`, you can pass:

- a raw filter string, or
- a `FilterExpression` built with `affinity.F`

```python
from affinity import Affinity, F

with Affinity(api_key="your-key") as client:
    companies = client.companies.list(filter=F.field("domain").contains("acme"))
    for c in companies.data:
        print(c.name)
```
