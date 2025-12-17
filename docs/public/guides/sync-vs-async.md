# Sync vs async

## Sync

Use `Affinity`:

```python
from affinity import Affinity

with Affinity(api_key="your-key") as client:
    for person in client.persons.all():
        print(person.first_name)
```

## Async

Use `AsyncAffinity`:

```python
from affinity import AsyncAffinity

async def main() -> None:
    async with AsyncAffinity(api_key="your-key") as client:
        async for company in client.companies.all():
            print(company.name)
```

## Parity

`AsyncAffinity` currently exposes a smaller service surface area than `Affinity`.

| Service | Sync (`Affinity`) | Async (`AsyncAffinity`) |
|---|:---:|:---:|
| companies | ✅ | ✅ |
| persons | ✅ | ✅ |
| lists | ✅ | ✅ |
| opportunities | ✅ | ✅ |
| tasks | ✅ | ✅ |
| notes | ✅ | ❌ |
| reminders | ✅ | ❌ |
| webhooks | ✅ | ❌ |
| interactions | ✅ | ❌ |
| fields | ✅ | ❌ |
| field_values | ✅ | ❌ |
| files | ✅ | ❌ |
| relationships | ✅ | ❌ |
| auth | ✅ | ❌ |

If you need a sync-only service today, use `Affinity` (sync) or contribute async support.

## Next steps

- [Getting started](../getting-started.md)
- [Examples](../examples.md)
- [API versions & routing](api-versions-and-routing.md)
