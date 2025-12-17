# Errors and retries

The SDK raises typed exceptions (subclasses of `AffinityError`) and retries some transient failures for safe methods (`GET`/`HEAD`).

## Exception taxonomy (common)

- `AuthenticationError` (401): invalid/missing API key
- `AuthorizationError` (403): insufficient permissions
- `NotFoundError` (404): entity or endpoint not found
- `ValidationError` (400/422): invalid parameters/payload
- `RateLimitError` (429): you are being rate limited (may include `retry_after`)
- `ServerError` (500/503): transient server-side errors
- `BetaEndpointDisabledError`: you called a beta V2 endpoint without `enable_beta_endpoints=True`
- `VersionCompatibilityError`: response parsing failed, often due to V2 API version mismatch

See [Exceptions](../reference/exceptions.md) for the full hierarchy.

## Retry policy (what is retried)

By default, retries apply to:

- `GET`/`HEAD` only (safe/idempotent methods)
- 429 responses (rate limits): respects `Retry-After` when present
- transient network/timeouts for `GET`/`HEAD`
- transient server errors (e.g., 5xx) for `GET`/`HEAD`

Retries are controlled by `max_retries` (default: 3).

## Diagnostics

Many errors include diagnostics (method/URL/status and more). When you catch an `AffinityError`, you can log it and inspect attached context.

```python
from affinity import Affinity
from affinity.exceptions import AffinityError, RateLimitError

try:
    with Affinity(api_key="your-key") as client:
        client.companies.list()
except RateLimitError as e:
    print("Rate limited:", e)
    print("Retry after:", e.retry_after)
except AffinityError as e:
    print("Affinity error:", e)
    if e.diagnostics:
        print("Request:", e.diagnostics.method, e.diagnostics.url)
        print("Status:", e.status_code)
        print("Request ID:", e.diagnostics.request_id)
```

## Rate limits

If you are consistently hitting 429s, see [Rate limits](rate-limits.md) for strategies and the rate limit APIs.

## API versions and beta endpoints

If you see `BetaEndpointDisabledError`, enable beta endpoints:

```python
from affinity import Affinity

client = Affinity(api_key="your-key", enable_beta_endpoints=True)
```

If you see `VersionCompatibilityError`, this often indicates a V2 API version mismatch between your API key settings and what the SDK expects. Check your API key’s “Default API Version”, and consider setting `expected_v2_version` for clearer diagnostics:

```python
from affinity import Affinity

client = Affinity(api_key="your-key", expected_v2_version="2024-01-01")
```

See [API versions & routing](api-versions-and-routing.md) and the [Glossary](../glossary.md).

## Next steps

- [Rate limits](rate-limits.md)
- [Troubleshooting](../troubleshooting.md)
- [Configuration](configuration.md)
- [API versions & routing](api-versions-and-routing.md)
- [Exceptions reference](../reference/exceptions.md)
