# Affinity Python SDK

A modern, strongly-typed Python wrapper for the Affinity CRM API.

## Install

```bash
pip install affinity-sdk
```

## Quickstart

```python
from affinity import Affinity
from affinity.types import FieldType

with Affinity(api_key="your-api-key") as client:
    for company in client.companies.all(field_types=[FieldType.ENRICHED]):
        print(company.name)
```

## Next steps

- [Getting started](getting-started.md)
- [Guides](guides/authentication.md)
- [API reference](reference/client.md)
