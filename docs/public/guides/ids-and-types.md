# IDs and types

The SDK uses strongly-typed IDs (Python `NewType`) to reduce accidental ID mixups.

```python
from affinity import Affinity
from affinity.types import CompanyId

with Affinity(api_key="your-key") as client:
    company = client.companies.get(CompanyId(123))
    print(company.name)
```

See `reference/types.md`.
