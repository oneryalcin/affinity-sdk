Show a quick reference for using the Affinity Python SDK and xaffinity CLI.

## IMPORTANT: Read-Only by Default

Always use read-only mode unless the user explicitly approves data modification. CRM data is sensitive!

## SDK Quick Start

```python
from affinity import Affinity, F
from affinity.types import PersonId, CompanyId, ListId
from affinity.policies import Policies, WritePolicy

# ALWAYS use read-only mode by default
with Affinity.from_env(policies=Policies(write=WritePolicy.DENY)) as client:
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
# API key: use --dotenv to load from .env file, or export AFFINITY_API_KEY
# ALWAYS use --readonly by default
xaffinity --dotenv --readonly person ls --all
xaffinity --dotenv --readonly company ls --all

# Export to CSV
xaffinity --dotenv --readonly person ls --all --csv people.csv

# JSON for scripting
xaffinity --dotenv --readonly person ls --json --all | jq '.data.persons[]'

# Filter custom fields
xaffinity --dotenv --readonly person ls --filter 'field("Dept") = "Sales"' --all
```

## Key Gotchas

1. **Read-only by default**: Only allow writes when user explicitly approves
2. **Use typed IDs**: `PersonId(123)` not `123`
3. **Use context manager**: `with Affinity() as client:`
4. **Filters only work on custom fields** - not `type`, `name`, `domain`, etc.
5. **CSV export requires `--all`**

## More Info

- SDK docs: https://yaniv-golan.github.io/affinity-sdk/
- CLI help: `xaffinity --help`
