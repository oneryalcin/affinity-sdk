# Rate limits

The SDK exposes a version-agnostic rate limit surface via `client.rate_limits`:
- `snapshot()` is best-effort and does not make network calls.
- `refresh()` makes one request and returns the best available snapshot.

## Snapshot (no network)

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    client.companies.list()
    print(client.rate_limits.snapshot())
```

## Refresh (one request)

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    limits = client.rate_limits.refresh()
    print(limits)
```

## Handling 429s

When the API returns 429, the SDK raises `RateLimitError` (and may retry safe methods).
See [Errors & retries](errors-and-retries.md).

## Next steps

- [Errors & retries](errors-and-retries.md)
- [Configuration](configuration.md)
- [Troubleshooting](../troubleshooting.md)
