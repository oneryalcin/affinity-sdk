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

For file downloads, you can override timeouts per call, and (for streaming downloads) set a total time budget:

```python
from affinity import Affinity
from affinity.types import FileId

with Affinity(api_key="your-key") as client:
    for chunk in client.files.download_stream(FileId(123), timeout=60.0, deadline_seconds=300):
        ...
```

To preserve server-provided file metadata (like filename and size), use `download_stream_with_info(...)`:

```python
from affinity import Affinity
from affinity.types import FileId

with Affinity(api_key="your-key") as client:
    downloaded = client.files.download_stream_with_info(FileId(123), timeout=60.0, deadline_seconds=300)
    filename = downloaded.filename or client.files.get(FileId(123)).name
    for chunk in downloaded.iter_bytes:
        ...
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
from affinity.hooks import HookEvent

def on_event(event: HookEvent) -> None:
    print(event.type)

client = Affinity(
    api_key="your-key",
    log_requests=True,
    on_event=on_event,
    hook_error_policy="swallow",  # or "raise"
)
```

Notes:

- For the synchronous client (`Affinity`), `on_event` must be a synchronous function. If it returns an awaitable, the SDK raises `ConfigurationError`.
- For the async client (`AsyncAffinity`), `on_event` can be sync or async.

Affinity downloads may redirect to externally-hosted signed URLs; external URLs are redacted in events by default.
If you want to change that behavior, configure `Policies(external_hooks=...)`:

```python
from affinity import Affinity, ExternalHookPolicy
from affinity.policies import Policies

client = Affinity(
    api_key="your-key",
    on_event=lambda e: print(e.type),
    policies=Policies(external_hooks=ExternalHookPolicy.REDACT),  # or SUPPRESS / EMIT_UNSAFE
)
```

## Disable writes (policy)

To guarantee the SDK does not perform write operations (POST/PUT/PATCH/DELETE, including uploads),
disable writes via policy:

```python
from affinity import Affinity
from affinity.policies import Policies, WritePolicy

client = Affinity(api_key="your-key", policies=Policies(write=WritePolicy.DENY))
```

## HTTP transport injection (advanced)

For testing/mocking without real network calls, inject an `httpx` transport:

```python
import httpx
from affinity import Affinity

def handler(request: httpx.Request) -> httpx.Response:
    if request.method == "GET" and request.url.path.endswith("/lists"):
        return httpx.Response(200, json={"data": [], "pagination": {}}, request=request)
    return httpx.Response(404, json={}, request=request)

client = Affinity(api_key="your-key", transport=httpx.MockTransport(handler))
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
