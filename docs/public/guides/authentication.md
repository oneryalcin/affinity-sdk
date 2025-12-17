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
