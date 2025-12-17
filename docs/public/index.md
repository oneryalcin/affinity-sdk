# Affinity Python SDK

A modern, strongly-typed Python wrapper for the Affinity CRM API.

Disclaimer: This is an unofficial community project and is not affiliated with, endorsed by, or sponsored by Affinity. “Affinity” and related marks are trademarks of their respective owners. Use of the Affinity API is subject to Affinity’s Terms of Service.

## Install

```bash
pip install affinity-sdk
```

Requires Python 3.10+.

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
