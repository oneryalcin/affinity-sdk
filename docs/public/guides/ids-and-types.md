# IDs and types

The SDK uses strongly-typed ID classes to reduce accidental ID mixups.

```python
from affinity import Affinity
from affinity.types import CompanyId

with Affinity(api_key="your-key") as client:
    company = client.companies.get(CompanyId(123))
    print(company.name)
```

See `reference/types.md`.

## Next steps

- [Field types & values](field-types-and-values.md)
- [Models](models.md)
- [Examples](../examples.md)
- [Types reference](../reference/types.md)
