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

## Timeouts and deadlines

- Use the global `timeout` to set a sensible default for API requests.
- For large file downloads, use per-call `timeout` and `deadline_seconds` to bound total time spent (including retries/backoff).

```python
from affinity import Affinity
from affinity.types import FileId

with Affinity(api_key="your-api-key", timeout=30.0) as client:
    for chunk in client.files.download_stream(FileId(123), timeout=60.0, deadline_seconds=300):
        ...
```

## Caching

The SDK provides optional in-memory caching for metadata-style responses (field definitions, list configurations). This reduces API calls for frequently-accessed, slowly-changing data.

### Enabling cache

```python
from affinity import Affinity

# Enable with default 5-minute TTL
client = Affinity(api_key="your-api-key", enable_cache=True)

# Custom TTL (in seconds)
client = Affinity(api_key="your-api-key", enable_cache=True, cache_ttl=600.0)
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

## Counting entities

### List entries (efficient)

Use `client.lists.get_size(list_id)` to get accurate entry counts:

```python
# Count entries on a single list
count = client.lists.get_size(list_id)
print(f"Entries: {count}")

# Get counts for multiple lists (cached for 5 min)
for lst in client.lists.all():
    count = client.lists.get_size(lst.id)
    print(f"{lst.name}: {count}")

# Force fresh fetch (bypass cache) when accuracy is critical
count = client.lists.get_size(list_id, force=True)
```

This uses the V1 API which returns accurate counts. Results are cached for 5 minutes per list. Use `force=True` to bypass the cache when you need the most up-to-date value.

### Global persons/companies (no direct method)

The Affinity API does not provide a count endpoint for global persons or companies. A `count()` method was intentionally omitted from the SDK because it would require paginating through all records—potentially hundreds of API calls for large databases.

**Why this matters:**

| Database size | API calls (V2) | Approximate time |
|---------------|----------------|------------------|
| 1,000 entities | 10 calls | ~1 second |
| 10,000 entities | 100 calls | ~10 seconds |
| 100,000 entities | 1,000 calls | ~2 minutes |

If you need a global count, iterate once and cache the result:

```python
# One-time count (expensive for large databases)
person_count = sum(1 for _ in client.persons.iter())
```

**Recommended alternatives:**

1. **Use lists**: Create a list containing your target entities and use `client.lists.get_size(list_id)`
2. **Cache externally**: Count once and store the result in your application
3. **Estimate**: If exact counts aren't critical, sample or track changes incrementally

## Next steps

- [Pagination](pagination.md)
- [Rate limits](rate-limits.md)
- [Errors & retries](errors-and-retries.md)
- [Configuration](configuration.md)
