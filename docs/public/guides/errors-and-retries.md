# Errors and retries

The SDK raises typed exceptions (subclasses of `AffinityError`) and retries some transient failures for safe methods (`GET`/`HEAD`).

## Exception taxonomy (common)

- `AuthenticationError` (401): invalid/missing API key
- `AuthorizationError` (403): insufficient permissions
- `NotFoundError` (404): entity or endpoint not found
- `ValidationError` (400/422): invalid parameters/payload
- `RateLimitError` (429): you are being rate limited (may include `retry_after`)
- `ServerError` (500/503): transient server-side errors
- `WriteNotAllowedError`: you attempted a write while writes are disabled by policy
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

## Download deadlines

For large file downloads, `timeout` controls per-request timeouts, and `deadline_seconds` enforces a total time budget for streaming downloads (including retries/backoff). When exceeded, the SDK raises `TimeoutError`.

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

## Production playbook

The SDK retries some failures for safe reads (`GET`/`HEAD`), but production systems typically need additional policies: alerting, bounded retries, idempotency for writes, and circuit breaking during outages.

### Recommended handling by error type

- **AuthenticationError (401), AuthorizationError (403)**: do not retry; fix credentials/permissions; alert immediately.
- **ValidationError (400/422)**: do not retry; treat as a bug or bad input; log the response body snippet for debugging.
- **NotFoundError (404)**: do not retry; treat as “missing” and handle at the business layer (or alert if it indicates data drift).
- **RateLimitError (429)**: retry only after `retry_after` (when present), reduce concurrency, and consider queueing/batching to smooth bursts.
- **Server errors (5xx) / transient network errors / timeouts**:
  - **Reads (`GET`/`HEAD`)**: retry with backoff (the SDK already does).
  - **Writes (`POST`/`PATCH`/`PUT`/`DELETE`)**: only retry if you can make the operation idempotent.
- **VersionCompatibilityError**: do not retry; fix API-version configuration (see below).

### Retrying writes safely (idempotency)

By default, the SDK does **not** retry non-`GET`/`HEAD` requests, because a retry can duplicate side effects (e.g., “create note” twice).

If you implement retries around writes, make them idempotent:

- Prefer endpoints that are naturally idempotent (e.g., “set field value to X” rather than “append note”).
- If the API supports an idempotency key header, use it (store the key per logical operation and reuse it on retry).
- If the API does not support idempotency keys, consider application-level deduping (e.g., deterministic external IDs, or checking for an existing resource before creating a new one).

### Circuit breaker (fail fast during outages)

For sustained 5xx/timeout/network failures, a circuit breaker can protect your system (and Affinity) from retry storms.

Minimal pattern:

```python
import time

class SimpleCircuitBreaker:
    def __init__(self, *, failure_threshold: int = 10, open_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._failures = 0
        self._open_until: float | None = None

    def allow(self) -> bool:
        if self._open_until is None:
            return True
        if time.monotonic() >= self._open_until:
            self._open_until = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._open_until = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._open_until = time.monotonic() + self.open_seconds
```

### Alerting guidance

Common triggers:

- Any sustained 401/403 (credentials/permissions regressions).
- Sustained 429s (rate-limit pressure): alert and reduce concurrency / increase backoff.
- Elevated 5xx/timeouts/network errors (provider outage or network problem).

When alerting, include `e.diagnostics.request_id` (when present) to speed up support/debugging.

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
