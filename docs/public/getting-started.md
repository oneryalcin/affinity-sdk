# Getting started

Requires Python 3.10+.

## Provide your API key

Set `AFFINITY_API_KEY`:

```bash
export AFFINITY_API_KEY="your-api-key"
```

Then create a client from the environment:

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

## Make your first request

This snippet covers authentication, a first request, and common failures:

```python
from affinity import Affinity
from affinity.exceptions import AuthenticationError, RateLimitError

try:
    with Affinity.from_env() as client:
        me = client.auth.whoami()
        print(f"Authenticated as: {me.user.email}")
except AuthenticationError:
    print("Check AFFINITY_API_KEY is set correctly")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}")
```

## Sync vs async

- Use `Affinity` for synchronous code.
- Use `AsyncAffinity` for async/await code.

See [Sync vs async](guides/sync-vs-async.md).

## Next steps

- [Authentication](guides/authentication.md)
- [Examples](examples.md)
- [Pagination](guides/pagination.md)
- [Errors & retries](guides/errors-and-retries.md)
- [Configuration](guides/configuration.md)
- [Filtering](guides/filtering.md)
- [Field types & values](guides/field-types-and-values.md)
- [V1 vs V2 routing](guides/v1-v2-routing.md)
- [API reference](reference/client.md)
