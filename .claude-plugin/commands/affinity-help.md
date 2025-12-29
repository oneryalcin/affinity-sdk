Show a quick reference for using the Affinity Python SDK and xaffinity CLI.

## SDK Quick Start

```python
from affinity import Affinity, F
from affinity.types import PersonId, CompanyId, ListId

with Affinity.from_env() as client:  # Uses AFFINITY_API_KEY env var
    # Identity
    me = client.whoami()

    # Iterate all companies
    for company in client.companies.all():
        print(company.name)

    # Filter (custom fields only)
    sales = client.persons.list(filter=F.field("Department").equals("Sales"))

    # Get by ID (use typed IDs!)
    person = client.persons.get(PersonId(123))
```

## CLI Quick Start

```bash
# Set API key
export AFFINITY_API_KEY="your-key"

# List entities
xaffinity person ls --all
xaffinity company ls --all

# Export to CSV
xaffinity person ls --all --csv people.csv

# JSON for scripting
xaffinity person ls --json --all | jq '.data.persons[]'

# Filter custom fields
xaffinity person ls --filter 'field("Dept") = "Sales"' --all
```

## Key Gotchas

1. **Use typed IDs**: `PersonId(123)` not `123`
2. **Use context manager**: `with Affinity() as client:`
3. **Filters only work on custom fields** - not `type`, `name`, `domain`, etc.
4. **CSV export requires `--all`**

## More Info

- SDK docs: https://yaniv-golan.github.io/affinity-sdk/
- CLI help: `xaffinity --help`
