# Models

Models are Pydantic v2 models. They validate API responses and give you typed attributes.

## Dumping data

Use `model_dump()` for Python objects and `model_dump(mode="json")` for JSON-safe output:

```python
from affinity import Affinity
from affinity.types import PersonId

with Affinity(api_key="your-key") as client:
    person = client.persons.get(PersonId(123))
    print(person.model_dump())
    print(person.model_dump(mode="json"))
```

## Aliases (camelCase vs snake_case)

The SDK accepts and populates both API-style keys (camelCase) and Python attribute names (snake_case) when parsing.

## Typed IDs

Many model `.id` fields use strongly-typed ID wrappers (for example: `PersonId`, `CompanyId`, `ListId`, `FieldValueId`).
They behave like `int` at runtime, but help static type checkers prevent mixing IDs across entity types.

```python
from affinity.types import (
    DropdownOptionId,
    FieldValueChangeId,
    FieldValueId,
    InteractionId,
    PersonId,
    TenantId,
)

person_id = PersonId(123)
interaction_id = InteractionId(456)
field_value_id = FieldValueId(789)
field_value_change_id = FieldValueChangeId(321)
dropdown_option_id = DropdownOptionId(10)
tenant_id = TenantId(99)
```

## Field values container

Entities like `Person`, `Company`, and `Opportunity` expose `fields`, which preserves whether you requested field data:

```python
from affinity import Affinity
from affinity.types import FieldType

with Affinity(api_key="your-key") as client:
    page = client.companies.list(field_types=[FieldType.GLOBAL])
    company = page.data[0]
    if company.fields.requested:
        print(company.fields.data)
```

## Next steps

- [Field types & values](field-types-and-values.md)
- [Models reference](../reference/models.md)
