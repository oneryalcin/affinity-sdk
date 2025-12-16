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
If you need a V1-only service (notes, reminders, webhooks, etc.), use the sync client or contribute async support.
