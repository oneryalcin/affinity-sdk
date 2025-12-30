# Filtering

V2 list endpoints accept `filter` expressions to query custom fields.

**Important:** V2 filters only work with **custom fields**, not built-in entity properties. Built-in properties like `type`, `firstName`, `domain`, etc. cannot be filtered.

## Recommended: Use the Filter Builder

Use `affinity.F` to build type-safe filter expressions:

```python
from affinity import Affinity, F

with Affinity(api_key="your-key") as client:
    # ✅ Recommended: Type-safe filter builder
    companies = client.companies.list(
        filter=F.field("Industry").equals("Software")
    )
```

Benefits of the filter builder:
- ✅ Prevents syntax errors with type checking
- ✅ Handles escaping automatically
- ✅ Makes it clear you're filtering custom fields (via `field()` method)
- ✅ Provides IDE autocomplete for filter operations

**CLI users:** The CLI uses raw filter string syntax. See [CLI commands reference](../cli/commands.md) for examples.

## Filter Builder Examples

**Simple comparisons:**

```python
from affinity import Affinity, F

# Equals
persons = client.persons.list(filter=F.field("Department").equals("Sales"))

# Contains (case-insensitive substring match)
companies = client.companies.list(filter=F.field("Industry").contains("Tech"))

# Starts with
persons = client.persons.list(filter=F.field("Title").starts_with("VP"))

# Greater than (for numbers/dates)
opportunities = client.opportunities.list(filter=F.field("Amount").greater_than(100000))

# Is null / is not null
persons = client.persons.list(filter=F.field("Manager").is_null())
```

**Complex logic (AND/OR/NOT):**

```python
# AND: Both conditions must be true
active_sales = client.persons.list(
    filter=F.field("Department").equals("Sales") & F.field("Status").equals("Active")
)

# OR: Either condition can be true
tech_or_finance = client.companies.list(
    filter=F.field("Industry").equals("Technology") | F.field("Industry").equals("Finance")
)

# NOT: Negate a condition
non_archived = client.persons.list(
    filter=~F.field("Archived").equals(True)
)

# Complex: (A AND B) OR (C AND D)
result = client.companies.list(
    filter=(
        (F.field("Industry").equals("Software") & F.field("Region").equals("US"))
        | (F.field("Industry").equals("Hardware") & F.field("Region").equals("EU"))
    )
)
```

**In list (multiple values):**

```python
# Match any value in the list
multi_region = client.companies.list(
    filter=F.field("Region").in_list(["US", "Canada", "Mexico"])
)
```

## Raw Filter Strings (Advanced)

For CLI or advanced SDK use, you can use raw filter strings:

| Meaning | Operator | Example |
|---|---|---|
| and | `&` | `field("A") = 1 & field("B") = 2` |
| or | `|` | `field("A") = 1 | field("B") = 2` |
| not | `!` | `!(field("A") = 1)` |
| equals | `=` | `field("Industry") = "Software"` |
| not equals | `!=` | `field("Status") != "inactive"` |
| starts with | `=^` | `field("Name") =^ "Ac"` |
| ends with | `=$` | `field("Name") =$ "Inc"` |
| contains | `=~` | `field("Title") =~ "Manager"` |
| is NULL | `!= *` | `field("Email") != *` |
| is not NULL | `= *` | `field("Email") = *` |

**CLI example:**
```bash
xaffinity person ls --filter 'Department = "Sales"'
```

**SDK with raw string:**
```python
# Less safe than using F, but works
persons = client.persons.list(filter='field("Department") = "Sales"')
```

## What can be filtered?

**✅ Custom fields** (added to entities in Affinity):

Python SDK:
- `F.field("Department").equals("Sales")`
- `F.field("Status").contains("Active")`

CLI (raw filter syntax):
- `Department = "Sales"`
- `Status =~ "Active"`

**❌ Built-in properties** (cannot be filtered with V2 filter expressions):
- Person: `type`, `firstName`, `lastName`, `primaryEmail`, `emailAddresses`
- Company: `name`, `domain`, `domains`
- Opportunity: `name`, `listId`

For built-in properties, retrieve all data and filter client-side (see [CSV Export Guide](./csv-export.md) for examples).

## Filtering in List Exports (CLI)

The `list export` command supports two filter options with **identical syntax** but different behavior:

| Option | What It Filters | Where Filtering Happens |
|--------|----------------|------------------------|
| `--filter` | List entries | Server-side (API) |
| `--expand-filter` | Expanded entities (people, companies) | Client-side (after fetch) |

### Why the difference?

The Affinity API supports filtering for list entries, but **does not support filtering associations**.

When you use `--expand people`, the CLI:

1. Fetches the list entries (can be filtered with `--filter`)
2. For each entry, fetches ALL associated people (API returns all, no filter option)
3. Filters the people locally based on `--expand-filter`

This means `--expand-filter`:

- Uses the same syntax as `--filter` for consistency
- Is applied after fetching data (doesn't reduce API calls)
- Still useful for reducing output size and focusing on relevant associations

### Supported operators for `--expand-filter`

| Syntax | Meaning | Example |
|--------|---------|---------|
| `=` | Exact match | `name=Alice` |
| `!=` | Not equal | `name!=Bob` |
| `=*` | IS NOT NULL (has value) | `email=*` |
| `!=*` | IS NULL (empty/not set) | `email!=*` |
| `=~` | Contains substring | `name=~Corp` |
| `\|` | OR | `status=Unknown \| status=Valid` |
| `&` | AND | `status=Valid & role=CEO` |
| `!` | NOT (prefix) | `!(status=Inactive)` |
| `()` | Grouping | `(status=A \| status=B) & role=CEO` |

### Example

```bash
# Server-side: only fetch Active opportunities
# Client-side: only include people with valid email status
xaffinity list export 275454 \
  --filter "Status=Active" \
  --expand people \
  --expand-filter "Primary Email Status=Valid | Primary Email Status=Unknown | Primary Email Status!=*" \
  --all --csv output.csv
```

### Performance consideration

Since `--expand-filter` is client-side, all associations are still fetched from the API.
For large lists with many associations, the export may take time even if the filter
reduces the final output significantly. Use `--dry-run` to estimate API calls.

## Next steps

- [Pagination](pagination.md)
- [Field types & values](field-types-and-values.md)
- [Examples](../examples.md)
- [Filters reference](../reference/filters.md)
