# Authentication

The SDK authenticates using an Affinity API key.

```python
from affinity import Affinity

with Affinity(api_key="your-api-key") as client:
    me = client.auth.whoami()
    print(me.user.email)
```

## Environment variables

If you prefer reading from the environment:

```python
from affinity import Affinity

client = Affinity.from_env()
```

## Next steps

- [Getting started](../getting-started.md)
- [Configuration](configuration.md)
- [Examples](../examples.md)
- [Errors & retries](errors-and-retries.md)
- [API reference](../reference/client.md)
