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

The SDK provides optional in-memory caching for metadata-style responses (field definitions, list configurations). This reduces API calls for frequently-accessed, slowly-changing data.

### Enabling cache

```python
from affinity import Affinity

# Enable with default 5-minute TTL
client = Affinity(api_key="your-key", enable_cache=True)

# Custom TTL (in seconds)
client = Affinity(api_key="your-key", enable_cache=True, cache_ttl=600.0)
```

### Long-running applications

For long-running processes (web servers, background workers), be aware that cached data may become stale:

- **Field definitions** may change if admins add/modify fields
- **List configurations** may change if lists are reconfigured
- **Default TTL is 5 minutes** (300 seconds)

Recommendations:

1. **Choose appropriate TTL**: Match your TTL to how often metadata changes in your organization
2. **Invalidate on known changes**: Clear cache after operations that modify metadata
3. **Periodic refresh**: For very long processes, consider periodic cache clears

### Manual cache invalidation

```python
# Clear all cached entries
client.clear_cache()
```

### When to use caching

| Scenario | Recommendation |
|----------|----------------|
| Short-lived scripts | Caching optional (few repeated calls) |
| CLI tools | Enable caching (reduces latency for field lookups) |
| Web servers | Enable with appropriate TTL |
| Background workers | Enable, consider periodic cache refresh |

### Cache isolation

Cache is isolated per API key and base URL combination, so multiple clients with different credentials won't share cached data.

### CLI session caching

For CLI pipelines, use session caching to share metadata across invocations:

```bash
export AFFINITY_SESSION_CACHE=$(xaffinity session start)
xaffinity list export "My List" | xaffinity person get
xaffinity session end
```

See [CLI Pipeline Optimization](../cli/commands.md#pipeline-optimization) for details.
