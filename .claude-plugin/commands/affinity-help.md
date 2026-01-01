---
name: affinity-help
description: Show quick reference for using the Affinity Python SDK and xaffinity CLI
allowed-tools: []
---

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

**Always use: `--dotenv --readonly --json`**

```bash
# Standard pattern for queries
xaffinity --dotenv --readonly person search "John Smith" --json
xaffinity --dotenv --readonly person get 123 --json
xaffinity --dotenv --readonly company get domain:acme.com --json

# Export to CSV (no --json needed)
xaffinity --dotenv --readonly person ls --all --csv people.csv

# Parse JSON with jq
xaffinity --dotenv --readonly person ls --json --all | jq '.data.persons[]'
```

## Key Gotchas

1. **Always use `--json`**: For structured, parseable output
2. **Always use `--readonly`**: Only allow writes when user explicitly approves
3. **Always use `--dotenv`**: Loads API key from .env file
4. **Use typed IDs (SDK)**: `PersonId(123)` not `123`
5. **Filters only work on custom fields** - not `type`, `name`, `domain`, etc.

## More Info

- SDK docs: https://yaniv-golan.github.io/affinity-sdk/
- CLI help: `xaffinity --help`
