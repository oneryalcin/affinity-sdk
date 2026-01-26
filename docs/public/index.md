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
    me = client.whoami()
    print(me.user.email)
```

## Next steps

- [Getting started](getting-started.md) - Authentication, first request, common patterns
- [Examples](examples.md)
- [CLI](cli/index.md)
- [AI Integrations](ai-integrations/index.md) - MCP Server & Claude Code plugins
- [Troubleshooting](troubleshooting.md)
- [API reference](reference/client.md)

## Guides

- [Authentication](guides/authentication.md) - API keys, env vars, context managers
- [Pagination](guides/pagination.md) - Iterating large result sets
- [Filtering](guides/filtering.md) - Filter query syntax
- [Field values](guides/field-values.md) - Custom field data
- [Errors & retries](guides/errors-and-retries.md) - Exception handling
- [Rate limits](guides/rate-limits.md) - Managing API quotas
- [Datetime handling](guides/datetime-handling.md) - Timezone behavior
- [Sync vs async](guides/sync-vs-async.md) - Choosing the right client
