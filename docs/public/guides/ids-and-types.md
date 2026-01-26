# IDs and types

The SDK uses strongly-typed ID classes to reduce accidental ID mixups and enable better static analysis.

## Basic usage

```python
from affinity import Affinity
from affinity.types import CompanyId, PersonId

with Affinity(api_key="your-api-key") as client:
    company = client.companies.get(CompanyId(123))
    person = client.persons.get(PersonId(456))
```

## Available ID types

| Type | Description |
|------|-------------|
| `PersonId` | Person identifier |
| `CompanyId` | Company identifier |
| `OpportunityId` | Opportunity identifier |
| `ListId` | List identifier |
| `ListEntryId` | List entry identifier |
| `FieldId` | Field definition identifier |
| `FieldValueId` | Field value identifier |
| `NoteId` | Note identifier |
| `InteractionId` | Interaction identifier |
| `FileId` | File attachment identifier |

## Why typed IDs?

Typed IDs help catch bugs at development time:

```python
from affinity.types import PersonId, CompanyId

person_id = PersonId(123)
company_id = CompanyId(456)

# Static type checkers will flag this as an error:
# client.persons.get(company_id)  # Wrong type!
```

## Behavior

Typed IDs behave like integers at runtime:

```python
from affinity.types import PersonId

pid = PersonId(123)
print(pid)       # 123
print(int(pid))  # 123
print(pid + 1)   # 124 (regular int)
```

## Next steps

- [Field types & values](field-types-and-values.md)
- [Models](models.md)
- [Examples](../examples.md)
- [Types reference](../reference/types.md)
