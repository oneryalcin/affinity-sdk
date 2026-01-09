---
name: affinity-help
description: Show quick reference for using the xaffinity CLI
allowed-tools: []
---

Show a quick reference for using the xaffinity CLI.

## IMPORTANT: Read-Only by Default

Always use `--readonly` unless the user explicitly approves data modification. CRM data is sensitive!

## CLI Quick Start

**First**: Run `xaffinity config check-key --json` to get the CLI pattern, then use it for all commands.

```bash
# Standard pattern for queries
xaffinity --readonly person ls --query "John Smith" --json
xaffinity --readonly person get 123 --json
xaffinity --readonly company get domain:acme.com --json

# Export to CSV (no --json needed)
xaffinity --readonly person ls --all --csv --csv-bom > people.csv

# Export list with associations
xaffinity --readonly list export LIST_ID --expand people --all --csv > output.csv

# Parse JSON with jq
xaffinity --readonly person ls --json --all | jq '.data.persons[]'
```

## Key Gotchas

1. **Always use `--json`**: For structured, parseable output
2. **Always use `--readonly`**: Only allow writes when user explicitly approves
3. **Use the pattern from `check-key`**: Run `xaffinity config check-key --json` and use the `pattern` field for all commands
4. **`--all` can be slow**: Exports with `--all` paginate through entire dataset - may take minutes for large CRMs
5. **`list export --filter` is client-side**: Fetches ALL data then filters locally (slow). Use `--saved-view` instead for large lists
6. **Filters only work on custom fields** - not `type`, `name`, `domain`, etc.
7. **Check `--help`**: Never guess command options

## Common Commands

| Task | Command |
|------|---------|
| Find person by email | `person get email:user@example.com` |
| Find company by domain | `company get domain:acme.com` |
| Export all contacts | `person ls --all --csv --csv-bom > contacts.csv` |
| Export pipeline | `list export LIST_ID --all --csv > out.csv` |

## More Info

- CLI help: `xaffinity --help`
- Command help: `xaffinity <command> --help` (e.g., `xaffinity person --help`)
- SDK docs: https://yaniv-golan.github.io/affinity-sdk/latest/
