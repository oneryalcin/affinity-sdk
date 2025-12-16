# Getting started

## Create a client

```python
from affinity import Affinity

client = Affinity(api_key="your-api-key")
```

Prefer the context manager to ensure resources are closed:

```python
from affinity import Affinity

with Affinity(api_key="your-api-key") as client:
    ...
```

## Sync vs async

- Use `Affinity` for synchronous code.
- Use `AsyncAffinity` for async/await code.

See [Sync vs async](guides/sync-vs-async.md).
