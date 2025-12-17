# Debugging hooks

You can attach request/response hooks for debugging and observability.

```python
from affinity import Affinity

def on_request(req) -> None:
    print("->", req.method, req.url)

def on_response(res) -> None:
    print("<-", res.status_code, res.request.url)

with Affinity(api_key="your-key", on_request=on_request, on_response=on_response) as client:
    client.companies.list()
```

## Next steps

- [Configuration](configuration.md)
- [Troubleshooting](../troubleshooting.md)
- [Errors & retries](errors-and-retries.md)
