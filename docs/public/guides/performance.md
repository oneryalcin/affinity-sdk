# Performance tuning

This guide covers practical knobs and patterns for high-volume usage.

## Pagination sizing

- Prefer larger `limit` values for throughput (fewer requests), but keep response sizes reasonable for your workload.
- If you hit 429s, lower concurrency first (see below), then consider reducing `limit`.

## Concurrency (async)

- Run independent reads concurrently, but cap concurrency (e.g., 5–20 in flight depending on rate limits and payload size).
- When you see 429s, reduce concurrency and let the SDK respect `Retry-After`.

## Connection pooling

The SDK uses httpx connection pooling. For high-throughput clients:

- Reuse a single client instance for many calls (don’t create a new `Affinity` per request).
- Close clients when done (use a context manager).

## HTTP/2

If your environment supports it, enabling HTTP/2 can improve performance for many small concurrent requests:

```python
from affinity import Affinity

client = Affinity(api_key="your-key", http2=True)
```

## Timeouts and deadlines

- Use the global `timeout` to set a sensible default for API requests.
- For large file downloads, use per-call `timeout` and `deadline_seconds` to bound total time spent (including retries/backoff).

```python
from affinity import Affinity
from affinity.types import FileId

with Affinity(api_key="your-key", timeout=30.0) as client:
    for chunk in client.files.download_stream(FileId(123), timeout=60.0, deadline_seconds=300):
        ...
```

## Caching

Caching is optional and currently targets metadata-style responses (for example, field metadata). If you enable it:

- Choose a TTL that matches how often you expect metadata to change.
- Consider clearing cache after known metadata changes (e.g., list/field configuration changes).
