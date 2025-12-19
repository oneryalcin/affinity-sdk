# Debugging hooks

You can attach request/response hooks for debugging and observability.

```python
from affinity import Affinity

def on_request(req) -> None:
    print("->", req.method, req.url)

def on_response(res) -> None:
    cache = " (cache hit)" if res.cache_hit else ""
    print("<-", res.status_code, res.request.url, cache)

def on_error(err) -> None:
    print("!!", type(err.error).__name__, err.request.url)

with Affinity(api_key="your-key", on_request=on_request, on_response=on_response, on_error=on_error) as client:
    client.companies.list()
```

If you need request interception for tests (without real network calls), use transport injection:

```python
import httpx
from affinity import Affinity

client = Affinity(api_key="your-key", transport=httpx.MockTransport(lambda req: httpx.Response(200)))
```

## Next steps

- [Configuration](configuration.md)
- [Troubleshooting](../troubleshooting.md)
- [Errors & retries](errors-and-retries.md)
