# Configuration

This guide documents the knobs exposed on `Affinity` / `AsyncAffinity`.

## Timeouts

```python
from affinity import Affinity

client = Affinity(api_key="your-key", timeout=60.0)
```

## Retries

- Retries apply to safe/idempotent methods (by default `GET`/`HEAD`).
- Tune with `max_retries`.

```python
from affinity import Affinity

client = Affinity(api_key="your-key", max_retries=5)
```

## Caching

Caching is optional and currently targets metadata-style responses (e.g., field metadata).

```python
from affinity import Affinity

client = Affinity(api_key="your-key", enable_cache=True, cache_ttl=300.0)
```

## Logging and hooks

```python
from affinity import Affinity

def on_request(req) -> None:
    print("->", req.method, req.url)

def on_response(res) -> None:
    print("<-", res.status_code, res.request.url)

client = Affinity(
    api_key="your-key",
    log_requests=True,
    on_request=on_request,
    on_response=on_response,
)
```

## V1/V2 URLs and auth mode

```python
from affinity import Affinity

client = Affinity(
    api_key="your-key",
    v1_base_url="https://api.affinity.co",
    v2_base_url="https://api.affinity.co/v2",
    v1_auth_mode="bearer",  # or "basic"
)
```

## Beta endpoints and version diagnostics

If you opt into beta endpoints or want stricter diagnostics around v2 response shapes:

```python
from affinity import Affinity

client = Affinity(
    api_key="your-key",
    enable_beta_endpoints=True,
    expected_v2_version="2024-01-01",
)
```

See also:

- [V1 vs V2 routing](v1-v2-routing.md)
- [Errors & retries](errors-and-retries.md)
