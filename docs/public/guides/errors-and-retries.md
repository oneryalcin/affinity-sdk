# Errors and retries

The SDK raises typed exceptions (subclasses of `AffinityError`) and retries some transient failures for safe methods (`GET`/`HEAD`).

## Exception taxonomy (common)

- `AuthenticationError` (401): invalid/missing API key
- `AuthorizationError` (403): insufficient permissions
- `NotFoundError` (404): entity or endpoint not found
- `ValidationError` (400/422): invalid parameters/payload
- `RateLimitError` (429): you are being rate limited (may include `retry_after`)
- `ServerError` (500/503): transient server-side errors

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
