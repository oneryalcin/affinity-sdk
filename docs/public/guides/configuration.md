# Configuration

This guide documents the knobs exposed on `Affinity` / `AsyncAffinity`.

## Load from environment

```python
from affinity import Affinity

client = Affinity.from_env()
```

To load a local `.env` file, install the optional extra and set `load_dotenv=True`:

```bash
pip install "affinity-sdk[dotenv]"
```

```python
from affinity import Affinity

client = Affinity.from_env(load_dotenv=True)
```

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

## Download redirects (files)

Affinity file downloads may redirect to externally-hosted signed URLs. By default, the SDK refuses `http://` redirects.

If you must allow insecure redirects (not recommended), opt in explicitly:

```python
from affinity import Affinity

client = Affinity(api_key="your-key", allow_insecure_download_redirects=True)
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

- [API versions & routing](api-versions-and-routing.md)
- [Errors & retries](errors-and-retries.md)

## Next steps

- [Getting started](../getting-started.md)
- [Debugging hooks](debugging-hooks.md)
- [Rate limits](rate-limits.md)
- [API reference](../reference/client.md)
