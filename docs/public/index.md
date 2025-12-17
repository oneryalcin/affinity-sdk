# Affinity Python SDK

A modern, strongly-typed Python wrapper for the Affinity CRM API.

## Install

```bash
pip install affinity-sdk
```

## Quickstart

```python
from affinity import Affinity

with Affinity(api_key="your-api-key") as client:
    me = client.auth.whoami()
    print(me.user.email)
```

## Next steps

- [Getting started](getting-started.md)
- [Examples](examples.md)
- [Troubleshooting](troubleshooting.md)
- [Guides](guides/authentication.md)
- [API reference](reference/client.md)
