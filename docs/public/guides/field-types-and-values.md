# Field types and values

Many endpoints can return “field values” in addition to the core entity shape.

## Field types

Use `FieldType` to request which field scopes you want:

```python
from affinity import Affinity
from affinity.types import FieldType, PersonId

with Affinity(api_key="your-key") as client:
    person = client.persons.get(PersonId(123), field_types=[FieldType.ENRICHED, FieldType.GLOBAL])
    if person.fields.requested:
        print(person.fields.data)
```

Common values include:

- `FieldType.ENRICHED`
- `FieldType.GLOBAL`
- `FieldType.LIST`
- `FieldType.LIST_SPECIFIC`

## Field IDs

If you know specific field IDs, you can request only those:

```python
from affinity import Affinity
from affinity.types import FieldId, FieldType

with Affinity(api_key="your-key") as client:
    page = client.companies.list(field_ids=[FieldId(101)], field_types=[FieldType.GLOBAL])
    for company in page.data:
        if company.fields.requested:
            print(company.fields.data.get("101"))
```

## Requested vs not requested

Entities expose a `fields` container that preserves whether the API returned field data:

- `entity.fields.requested == False`: you didn’t request fields (or the API omitted them)
- `entity.fields.requested == True`: field data was requested and returned (possibly empty)

## Next steps

- [Filtering](filtering.md)
- [Models](models.md)
- [Types reference](../reference/types.md)
