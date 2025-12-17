# Rate limits

The SDK tracks rate-limit state from responses and can also query rate-limit status via the API.

## Local tracking

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    client.companies.list()
    print(client.rate_limit_state)
```

## Query current limits

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    limits = client.auth.get_rate_limits()
    print(limits)
```

## Handling 429s

When the API returns 429, the SDK raises `RateLimitError` (and may retry safe methods).
See [Errors & retries](errors-and-retries.md).

## Next steps

- [Errors & retries](errors-and-retries.md)
- [Configuration](configuration.md)
- [Troubleshooting](../troubleshooting.md)
