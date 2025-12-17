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

## Field value type mapping

When you read `entity.fields.data`, values are typed as `Any`. The expected shape depends on the field’s `valueType`
(`FieldValueType`) and whether the field allows multiple values.

| Affinity `FieldValueType` | Typical Python value | Notes |
|---|---|---|
| `TEXT` / `FILTERABLE_TEXT` | `str` | Plain text |
| `NUMBER` | `int \| float` | JSON number |
| `DATE` | `str` / `datetime.date` | Typically ISO-8601 date strings on read; `date` is convenient on write |
| `PERSON` | `PersonId` / `list[PersonId]` | Under the hood: `int` or `list[int]` |
| `ORGANIZATION` | `CompanyId` / `list[CompanyId]` | Under the hood: `int` or `list[int]` |
| `DROPDOWN` | `int` / `list[int]` | Dropdown option IDs (ranked dropdown) |
| `LOCATION` | `dict[str, str]` | Typically a structured object (shape varies by API) |

## Next steps

- [Filtering](filtering.md)
- [Models](models.md)
- [Types reference](../reference/types.md)
