---
name: querying-affinity-crm
description: Use this skill when the user asks about "Affinity", "Affinity CRM", "xaffinity", "affinity-sdk", or wants to search, find, get, show, or export people, persons, contacts, companies, organizations, deals, opportunities, lists, pipelines, or CRM data from Affinity. Also use when writing Python scripts with the Affinity SDK or running xaffinity CLI commands.
---

# REQUIRED FIRST STEP: Verify API Key

**STOP. Before doing ANYTHING else, run this command:**

```bash
xaffinity config check-key --json
```

This MUST be your first action when handling any Affinity request. Do not skip this step.

**If `"configured": true`** - Use the `pattern` field from the output for ALL subsequent commands. Example:
- If `"pattern": "xaffinity --dotenv --readonly <command> --json"` → use `--dotenv`
- If `"pattern": "xaffinity --readonly <command> --json"` → no `--dotenv` needed

Then proceed with the user's request below.

**If `"configured": false` or exit code 1** - Stop and help the user set up their API key:

1. Tell them: "You need to configure an Affinity API key first."
2. Direct them to get a key: Affinity → Settings → API → Generate New Key
3. **Tell them to run this command themselves** (do NOT run it for them):
   ```
   xaffinity config setup-key
   ```
4. Wait for them to confirm setup is complete, then re-run `check-key --json` to verify

**IMPORTANT**: The `setup-key` command is interactive - it uses secure hidden input that only works in the user's terminal. Do NOT try to run it yourself. Just tell the user to run it.

**SECURITY**: Never ask users to paste API keys in chat. The setup command keeps keys private.

---

# Querying Affinity CRM

The Affinity Python SDK (`affinity` package) and CLI (`xaffinity`) provide access to Affinity CRM data.

## Critical Patterns

- **Read-only mode**: Always use `--readonly` unless user explicitly requests writes
- **JSON output**: Always include `--json` for structured, parseable output
- **Filtering**: `--filter` works only on **custom fields**, not built-in properties (`name`, `email`, etc.). For `list export`, filtering is **client-side** (see Gotchas)
- **Timezones**: API returns UTC. Convert to user's local timezone or state "UTC"

**For Python scripts**: See [SDK_REFERENCE.md](SDK_REFERENCE.md) for SDK patterns, typed IDs, and async support.

## Gotchas & Workarounds

### Internal user meetings are NOT in interactions
The interactions API only shows meetings with **external** contacts. Team-only meetings won't appear.
```bash
# Returns NOTHING for internal-only meetings:
interaction ls --person-id 123 --type meeting --start-time 2025-01-01 --end-time 2025-12-31
```
**Workaround:** Use notes: `note ls --person-id 123` and filter for `isMeeting: true`

### Interactions require BOTH start-time AND end-time (max 1 year)
```bash
# WRONG - will error:
interaction ls --person-id 123 --type meeting

# CORRECT:
interaction ls --person-id 123 --type meeting --start-time 2025-01-01 --end-time 2025-12-31
```

### Smart Fields (Last Meeting, Next Meeting) are NOT in the API
These UI-only calculated fields don't exist in the API.
**Workaround:** Use `--with-interaction-dates` on person/company search:
```bash
person search "Alice" --with-interaction-dates
company search "Acme" --with-interaction-dates
```

### Opportunities can only be in ONE list (created with it)
Unlike persons/companies, opportunities are tightly coupled to their list:
- Creating an opportunity requires `--list-id` and auto-creates the list entry
- Deleting the opportunity = removing from list (same operation)
- Cannot move/copy an opportunity to another list

```bash
# CREATE a new opportunity (automatically added to the specified list):
opportunity create --list-id LIST_ID --name "Deal Name"
```

### Global organizations are read-only
Companies marked `global: true` cannot have their name/domain changed or be deleted.

### Field definitions cannot be created/updated via API
Must use Affinity web UI to create or modify field definitions.

### List entry filtering is client-side (performance tip)
The Affinity API does **not** support server-side filtering on list entries. When you use `--filter` with `list export`, all entries are fetched first, then filtered locally.

**Optimization:** If you need multiple different filtered views of the same list, fetch once and post-process:
```bash
# INEFFICIENT - 3 API round-trips fetching the same data:
list export 123 --filter 'Status = "New"' --all --json > new.json
list export 123 --filter 'Status = "Active"' --all --json > active.json
list export 123 --filter 'Status = "Closed"' --all --json > closed.json

# BETTER - 1 API call, then filter locally with jq:
list export 123 --all --json > all.json
jq '[.[] | select(.Status == "New")]' all.json > new.json
jq '[.[] | select(.Status == "Active")]' all.json > active.json
jq '[.[] | select(.Status == "Closed")]' all.json > closed.json

# OR use a combined filter and split afterward:
list export 123 --filter 'Status = "New" | Status = "Active"' --all --json > subset.json
```

For true server-side filtering, use **saved views** (`--saved-view`) configured in the Affinity web UI.

## CLI Quick Reference

**Use the `pattern` from check-key output** (includes `--dotenv` only if needed):

```bash
# Replace <command> in the pattern from check-key:
# If pattern was "xaffinity --dotenv --readonly <command> --json":
xaffinity --dotenv --readonly person search "John Smith" --json

# If pattern was "xaffinity --readonly <command> --json":
xaffinity --readonly person search "John Smith" --json
```

**IMPORTANT: Use `--help` to discover options. Never guess.**

```bash
xaffinity person --help              # See all person subcommands
xaffinity list export --help         # See export options
```

**Common commands** (using pattern from check-key):

```bash
# Get by ID or identifier
person get 123                       # By ID
person get email:alice@example.com   # By email
company get domain:acme.com          # By domain

# List/search
person search "John Smith"
company ls --all
list export LIST_ID --all

# Export to CSV (no --json needed)
person ls --all --csv people.csv --csv-bom

# Filter on custom fields
person ls --filter 'Department = "Sales"' --all
```

See [CLI_REFERENCE.md](CLI_REFERENCE.md) for complete command reference.

## Common Workflows

**Use CLI options directly.** Don't write Python scripts for simple export tasks.

### Export list entries with associated entities
```bash
# Export opportunity list with associated people (add --dotenv if check-key indicated)
list export LIST_ID --expand people --all --csv output.csv --csv-bom

# Export with both people and companies
list export LIST_ID --expand people --expand companies --all --csv output.csv
```

**Valid expand values:** `people` (opportunity/company lists), `companies` (opportunity/person lists)

See [LIST_EXPORT_EXPAND.md](LIST_EXPORT_EXPAND.md) for detailed options.

### Export list entries filtered by custom field
```bash
list export LIST_ID --filter 'Status = "Active"' --all --csv output.csv --csv-bom

# Combine filter with expand
list export LIST_ID --expand people --filter 'Status = "Active"' --all --csv out.csv
```

**Filter syntax:** `=` exact, `=~` contains, `=^` starts, `=$` ends, `!= *` NULL, `&` AND, `|` OR

### Export all contacts to CSV
```bash
person ls --all --csv contacts.csv --csv-bom
```

### Find person by email
```bash
person get email:alice@example.com
```

### List meetings for a person

**Interactions** - meetings with external participants (max 1-year range):
```bash
interaction ls --person-id 123 --type meeting --start-time 2025-01-01 --end-time 2025-12-31
```

**Notes** - internal-only meetings or meeting notes:
```bash
note ls --person-id 123   # Filter for isMeeting: true
```

## Reference Files

- [CLI_REFERENCE.md](CLI_REFERENCE.md) - Complete CLI command reference
- [LIST_EXPORT_EXPAND.md](LIST_EXPORT_EXPAND.md) - List export with expansions
- [SDK_REFERENCE.md](SDK_REFERENCE.md) - **Python scripts only** (typed IDs, async, error handling)
- Documentation: https://yaniv-golan.github.io/affinity-sdk/
