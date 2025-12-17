# Filtering

For V2 list endpoints that accept `filter`, you can pass:

- a raw filter string, or
- a `FilterExpression` built with `affinity.F`

## Operator reference

The builder outputs Affinity’s V2 filtering language:

| Meaning | Operator | Example |
|---|---|---|
| and | `&` | `foo = 1 & bar = 2` |
| or | `|` | `foo = 1 | bar = 2` |
| not | `!` | `!(foo = 1)` |
| equals | `=` | `name = "Acme"` |
| not equals | `!=` | `status != "inactive"` |
| starts with | `=^` | `name =^ "Ac"` |
| ends with | `=$` | `name =$ "me"` |
| contains | `=~` | `name =~ "cm"` |
| is NULL | `!= *` | `email != *` |
| is not NULL | `= *` | `email = *` |

```python
from affinity import Affinity, F

with Affinity(api_key="your-key") as client:
    companies = client.companies.list(filter=F.field("domain").contains("acme"))
    for c in companies.data:
        print(c.name)
```

## Next steps

- [Pagination](pagination.md)
- [Field types & values](field-types-and-values.md)
- [Examples](../examples.md)
- [Filters reference](../reference/filters.md)
