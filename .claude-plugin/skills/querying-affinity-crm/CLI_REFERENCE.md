# CLI Reference

Complete command reference for the `xaffinity` CLI.

## Installation and Setup

```bash
pip install affinity-sdk
```

**API Key options (choose one):**
```bash
# Option 1: Environment variable
export AFFINITY_API_KEY="your-api-key"

# Option 2: Use --dotenv to load from .env file in current directory
xaffinity --dotenv whoami

# Option 3: Read from file
xaffinity --api-key-file ~/.affinity-key whoami
```

## Read-Only Mode (IMPORTANT)

**Always use `--readonly` by default** to prevent accidental data modification:

```bash
# RECOMMENDED: Use --readonly for all read operations
xaffinity --readonly person ls --all
xaffinity --readonly company get 123
xaffinity --readonly list export 12345 --all --csv entries.csv

# Only omit --readonly when user explicitly approves writes
xaffinity person create --first-name Ada --last-name Lovelace
```

## Global Options

| Option | Description |
|--------|-------------|
| `--readonly` | **Recommended** - Prevent write operations |
| `--json` | Output machine-readable JSON |
| `--quiet` / `-q` | Suppress non-essential output |
| `--trace` | Show request/response traces |
| `--beta` | Enable beta endpoints |
| `--all` | Fetch all pages |
| `--csv <path>` | Export to CSV (requires `--all`) |
| `--csv-bom` | Add UTF-8 BOM for Excel |

## Timezone Note

**All datetimes from the API are in UTC.** When displaying to users:
- Convert to user's local timezone or clearly state "UTC"
- Example: `2025-12-30T13:00:00Z` (UTC) = 3:00 PM Israel time, 5:00 AM PST

## Identity

```bash
xaffinity whoami
xaffinity whoami --json
```

## People

```bash
# List all
xaffinity person ls
xaffinity person ls --all
xaffinity person ls --all --csv people.csv

# Search
xaffinity person search "alice@example.com"
xaffinity person search "Alice Smith" --all

# Get by ID
xaffinity person get 123
xaffinity person get 123 --all-fields

# Get by resolver
xaffinity person get email:alice@example.com
xaffinity person get 'name:"Alice Smith"'

# Get with expansions
xaffinity person get 123 --expand lists
xaffinity person get 123 --expand list-entries --list "Pipeline"
xaffinity person get 123 --expand list-entries --list-entry-field Stage

# Create
xaffinity person create --first-name Ada --last-name Lovelace --email ada@example.com

# Update
xaffinity person update 123 --email new@example.com

# Delete
xaffinity person delete 123

# Merge (requires --beta)
xaffinity --beta person merge 111 222
```

## Companies

```bash
# List all
xaffinity company ls
xaffinity company ls --all --csv companies.csv

# Search
xaffinity company search "Acme"

# Get by ID
xaffinity company get 456
xaffinity company get 456 --all-fields

# Get by resolver
xaffinity company get domain:acme.com
xaffinity company get 'name:"Acme Corp"'

# Get with expansions
xaffinity company get 456 --expand lists
xaffinity company get 456 --expand people

# Create
xaffinity company create --name "New Corp" --domain newcorp.com

# Update
xaffinity company update 456 --domain updated.com

# Delete
xaffinity company delete 456
```

## Lists

```bash
# List all lists
xaffinity list ls

# Get list details
xaffinity list view 789
xaffinity list view 'name:"Deal Pipeline"'

# Get list fields
xaffinity list fields 789

# Export list entries
xaffinity list export 789 --all
xaffinity list export 789 --all --csv entries.csv
```

### List Export with Expansions

Export list entries with associated people/companies using `--expand`:

```bash
# Export with associated people
xaffinity list export LIST_ID --expand people --all --csv output.csv --csv-bom

# Export with both people and companies (opportunity lists)
xaffinity list export LIST_ID --expand people --expand companies --all --csv output.csv

# Combine with filters
xaffinity list export LIST_ID --expand people \
  --filter 'Status = "Active"' \
  --all --csv active_with_people.csv --csv-bom
```

**Valid expand values:** `people` (opportunity/company lists), `companies` (opportunity/person lists)

See [LIST_EXPORT_EXPAND.md](LIST_EXPORT_EXPAND.md) for detailed options: CSV modes, field expansion, association limits, error handling.

See [Filtering](#filtering) section for filter syntax reference.

## Opportunities

```bash
# List all
xaffinity opportunity ls
xaffinity opportunity ls --all --csv opps.csv

# Get by ID
xaffinity opportunity get 321

# Create (requires list ID)
xaffinity opportunity create --list-id 789 --name "New Deal"
```

## Field Values

```bash
# List field values
xaffinity field-value ls --field-id 123

# Get specific value
xaffinity field-value get 456

# Create/update
xaffinity field-value create --field-id 123 --entity-id 456 --value "New Value"
xaffinity field-value update 789 --value "Updated"

# Delete
xaffinity field-value delete 789
```

## Notes

```bash
# List notes
xaffinity note ls --person-id 123
xaffinity note ls --company-id 456

# Create note
xaffinity note create --person-id 123 --content "Meeting notes"
```

## Interactions (Meetings, Emails, Calls)

**Use interactions for meetings, emails, and calls** - auto-synced from calendars and email.

**CRITICAL requirements:**
- **Both `--start-time` AND `--end-time` are REQUIRED** (API will error without them)
- **Maximum date range is 1 year** - start and end must be within 1 year of each other
- Interactions only appear if **at least one external contact** was involved
- Internal-only meetings (team members only) won't appear unless logged with a note
- Sync lag: Google Calendar ~30 min, Office365 up to 2 hours

```bash
# List meetings for a person in 2025 (MUST specify date range, max 1 year)
xaffinity --dotenv --readonly interaction ls --person-id 123 --type meeting \
  --start-time 2025-01-01 --end-time 2025-12-31 --json

# For multiple years, query each year separately
xaffinity --dotenv --readonly interaction ls --person-id 123 --type meeting \
  --start-time 2024-01-01 --end-time 2024-12-31 --json

# Other interaction types (same date range requirements)
xaffinity --dotenv --readonly interaction ls --person-id 123 --type email \
  --start-time 2025-01-01 --end-time 2025-12-31 --json
xaffinity --dotenv --readonly interaction ls --person-id 123 --type call \
  --start-time 2025-01-01 --end-time 2025-12-31 --json
```

Interaction types: `meeting`, `email`, `call`, `chat-message` (or `chat`)

**Alternatives for internal users:**
- Use notes with `isMeeting: true` for meeting records
- Use Smart Fields (`Last Meeting`, `Next Meeting`) on person/company records

## URL Resolution

```bash
# Parse Affinity UI URLs
xaffinity resolve-url "https://app.affinity.co/companies/123"
xaffinity resolve-url "https://mydomain.affinity.com/persons/456"
```

## Filtering

**Custom fields only** (built-in properties like `type`, `name`, `domain` cannot be filtered server-side):

```bash
# Equals (quote field names with spaces)
xaffinity person ls --filter 'Department = "Sales"' --all
xaffinity person ls --filter '"Primary Email Status" = "Valid"' --all

# Contains
xaffinity company ls --filter 'Industry =~ "Tech"' --all

# Starts with
xaffinity person ls --filter 'Title =^ "VP"' --all

# AND / OR
xaffinity person ls --filter 'Dept = "Sales" & Status = "Active"' --all
xaffinity company ls --filter 'Region = "US" | Region = "EU"' --all

# NOT
xaffinity person ls --filter '!(Archived = true)' --all

# NULL checks
xaffinity person ls --filter 'Manager != *' --all   # is null
xaffinity person ls --filter 'Manager = *' --all    # is not null
```

## Filter Operators Reference

| Meaning | Operator | Example |
|---------|----------|---------|
| equals | `=` | `Status = "Active"` |
| not equals | `!=` | `Status != "Closed"` |
| contains | `=~` | `Name =~ "Corp"` |
| starts with | `=^` | `Name =^ "Ac"` |
| ends with | `=$` | `Name =$ "Inc"` |
| is null | `!= *` | `Email != *` |
| is not null | `= *` | `Email = *` |
| is empty | `= ""` | `Notes = ""` |
| AND | `&` | `A = 1 & B = 2` |
| OR | `\|` | `A = 1 \| B = 2` |
| NOT | `!` | `!(A = 1)` |

**Note:** Field names with spaces must be quoted: `"Primary Email Status" = "Valid"`

## JSON Output for Scripting

All commands support `--json` for machine-readable output:

```bash
# Get JSON
xaffinity person ls --json --all

# Pipe to jq
xaffinity person ls --json --all | jq '.data.persons[]'
xaffinity company get 123 --json | jq '.data.company.name'

# Filter built-in properties with jq (since --filter only works on custom fields)
xaffinity person ls --json --all | jq '.data.persons[] | select(.type == "internal")'
xaffinity company ls --json --all | jq '.data.companies[] | select(.domain | endswith(".com"))'

# Custom CSV with jq
xaffinity person ls --json --all | jq -r '.data.persons[] | [.id, .name, .primaryEmail] | @csv'
```

## JSON Data Structure

```json
{
  "data": {
    "persons": [...],     // for person ls
    "companies": [...],   // for company ls
    "opportunities": [...],
    "person": {...},      // for person get
    "company": {...}      // for company get
  }
}
```

## CSV Export

```bash
# Basic export
xaffinity person ls --all --csv people.csv
xaffinity company ls --all --csv companies.csv
xaffinity opportunity ls --all --csv opps.csv
xaffinity list export 123 --all --csv entries.csv

# Excel-compatible (UTF-8 BOM)
xaffinity person ls --all --csv people.csv --csv-bom
```

**Note**: `--csv` requires `--all` to fetch all pages.
