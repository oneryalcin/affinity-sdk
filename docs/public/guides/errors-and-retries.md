# Errors and retries

The HTTP client retries some transient failures (e.g. rate limits) and raises typed exceptions.

```python
from affinity import Affinity
from affinity.exceptions import RateLimitError, AffinityError

try:
    with Affinity(api_key="your-key") as client:
        client.companies.list()
except RateLimitError as e:
    print("Rate limited:", e)
except AffinityError as e:
    print("Affinity error:", e)
```

See `reference/exceptions.md`.

See also [Exceptions](../reference/exceptions.md).
