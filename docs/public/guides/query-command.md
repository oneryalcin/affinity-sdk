# Query Command

The `xaffinity query` command provides a structured JSON query language for complex data retrieval, filtering, includes, and aggregations.

## When to Use Query vs Individual Commands

**Use `query` when you need:**
- Complex filtering with multiple AND/OR/NOT conditions
- Related entity data (include companies with persons)
- Aggregations (count, sum, avg, groupBy)
- Multi-field sorting
- Analysis across large datasets

**Use individual commands for:**
- Simple lookups (`person get 123`)
- Basic searches (`company ls --query "Acme"`)
- Quick exports (`list export Pipeline`)

## Basic Usage

```bash
# From file
xaffinity query --file query.json

# Inline JSON
xaffinity query --query '{"from": "persons", "limit": 10}'

# From stdin (piped)
echo '{"from": "persons"}' | xaffinity query

# Dry-run to preview execution plan
xaffinity query --file query.json --dry-run
```

## Query Structure

A minimal query requires only the `from` field:

```json
{
  "from": "persons"
}
```

A complete query can include:

```json
{
  "$version": "1.0",
  "from": "persons",
  "where": { "path": "email", "op": "contains", "value": "@acme.com" },
  "include": ["companies"],
  "select": ["id", "firstName", "lastName", "email"],
  "orderBy": [{ "field": "lastName", "direction": "asc" }],
  "limit": 100
}
```

### Supported Entity Types

| Entity | Description |
|--------|-------------|
| `persons` | People in your CRM |
| `companies` | Companies/organizations |
| `opportunities` | Deals/opportunities |
| `listEntries` | Entries in Affinity lists |
| `interactions` | Emails, calls, meetings |
| `notes` | Notes on entities |

## Filtering with WHERE

### Simple Conditions

```json
{
  "from": "persons",
  "where": { "path": "email", "op": "contains", "value": "@gmail.com" }
}
```

### Supported Operators

| Operator | Description | Example Value |
|----------|-------------|---------------|
| `eq` | Equals | `"Active"` |
| `neq` | Not equals | `"Closed"` |
| `gt` | Greater than | `10000` |
| `gte` | Greater than or equal | `10000` |
| `lt` | Less than | `5000` |
| `lte` | Less than or equal | `5000` |
| `contains` | Contains substring | `"@gmail"` |
| `starts_with` | Starts with | `"Acme"` |
| `in` | Value in list | `["New", "Active"]` |
| `between` | Value in range | `[1000, 5000]` |
| `is_null` | Field is null | (no value needed) |
| `is_not_null` | Field is not null | (no value needed) |
| `contains_any` | Array contains any | `["vip", "hot"]` |
| `contains_all` | Array contains all | `["verified", "active"]` |

### Compound Conditions

**AND:**

```json
{
  "from": "persons",
  "where": {
    "and_": [
      { "path": "email", "op": "is_not_null" },
      { "path": "firstName", "op": "starts_with", "value": "J" }
    ]
  }
}
```

**OR:**

```json
{
  "from": "persons",
  "where": {
    "or_": [
      { "path": "email", "op": "contains", "value": "@acme.com" },
      { "path": "email", "op": "contains", "value": "@acme.io" }
    ]
  }
}
```

**NOT:**

```json
{
  "from": "persons",
  "where": {
    "not_": { "path": "status", "op": "eq", "value": "Inactive" }
  }
}
```

### Field Paths

Access nested fields with dot notation:

```json
{
  "from": "listEntries",
  "where": { "path": "fields.Status", "op": "eq", "value": "Active" }
}
```

Array access:

```json
{
  "from": "persons",
  "where": { "path": "emails[0]", "op": "contains", "value": "@" }
}
```

### Date Filtering

**Relative dates:**

```json
{
  "from": "interactions",
  "where": { "path": "created_at", "op": "gte", "value": "-30d" }
}
```

| Format | Meaning |
|--------|---------|
| `-30d` | 30 days ago |
| `+7d` | 7 days from now |
| `today` | Start of today |
| `now` | Current time |
| `yesterday` | Start of yesterday |
| `tomorrow` | Start of tomorrow |

## Including Related Entities

Fetch related entities in a single query:

```json
{
  "from": "persons",
  "include": ["companies", "opportunities"],
  "limit": 50
}
```

### Available Relationships

| From | Can Include |
|------|-------------|
| `persons` | `companies`, `opportunities`, `interactions`, `notes` |
| `companies` | `persons`, `opportunities`, `interactions`, `notes` |
| `opportunities` | `persons`, `companies`, `interactions`, `notes` |

**Warning:** Includes cause N+1 API calls (one per parent record). Use `--dry-run` to preview the cost.

## Aggregations

### Basic Aggregates

```json
{
  "from": "opportunities",
  "aggregate": {
    "total": { "count": true },
    "totalValue": { "sum": "amount" },
    "avgValue": { "avg": "amount" }
  }
}
```

### Group By

```json
{
  "from": "opportunities",
  "groupBy": "status",
  "aggregate": {
    "count": { "count": true },
    "totalValue": { "sum": "amount" }
  }
}
```

### Having (Filter Aggregated Results)

```json
{
  "from": "opportunities",
  "groupBy": "status",
  "aggregate": {
    "count": { "count": true }
  },
  "having": { "path": "count", "op": "gte", "value": 5 }
}
```

## Sorting

```json
{
  "from": "persons",
  "orderBy": [
    { "field": "lastName", "direction": "asc" },
    { "field": "firstName", "direction": "asc" }
  ]
}
```

## Limiting Results

```json
{
  "from": "persons",
  "limit": 100
}
```

## Dry-Run Mode

**Always preview expensive queries first:**

```bash
xaffinity query --file query.json --dry-run
```

Output shows:

```
Query Execution Plan

Query:
  $version: 1.0
  from: persons
  include: [companies]
  limit: 100

Steps:
  [1] FETCH persons (1 API call)
  [2] FILTER (client-side)
  [3] INCLUDE companies (up to 100 API calls)
  [4] LIMIT 100

Estimated:
  API Calls: 101
  Records: 100

[warning] Include 'companies' will make N API calls (1 per person).
```

## Output Formats

```bash
# Table (default for interactive)
xaffinity query --file query.json

# JSON output
xaffinity query --file query.json --json

# CSV output
xaffinity query --file query.json --csv

# Pretty JSON with metadata
xaffinity query --file query.json --json --pretty --include-meta
```

## Command Options

| Option | Description |
|--------|-------------|
| `--file`, `-f` | Read query from JSON file |
| `--query` | Inline JSON query string |
| `--query-version` | Override `$version` in query |
| `--dry-run` | Show execution plan without running |
| `--dry-run-verbose` | Show detailed plan with API call breakdown |
| `--confirm` | Require confirmation before expensive operations |
| `--max-records` | Safety limit on total records (default: 10000) |
| `--timeout` | Overall timeout in seconds (default: 300) |
| `--json` | Output as JSON |
| `--csv` | Output as CSV |
| `--output` | Output format: table, json |
| `--pretty` | Pretty-print JSON output |
| `--include-meta` | Include execution metadata in output |
| `--quiet`, `-q` | Suppress progress output |
| `--verbose`, `-v` | Show detailed progress |

## Examples

### Find VIP Contacts at Tech Companies

```json
{
  "from": "persons",
  "where": {
    "and_": [
      { "path": "fields.VIP", "op": "eq", "value": true },
      { "path": "email", "op": "is_not_null" }
    ]
  },
  "include": ["companies"],
  "orderBy": [{ "field": "lastName", "direction": "asc" }],
  "limit": 100
}
```

### Pipeline Summary by Status

```json
{
  "from": "listEntries",
  "where": { "path": "listId", "op": "eq", "value": 12345 },
  "groupBy": "fields.Status",
  "aggregate": {
    "count": { "count": true },
    "totalValue": { "sum": "fields.Deal Value" }
  }
}
```

### Recent Meeting Interactions

```json
{
  "from": "interactions",
  "where": {
    "and_": [
      { "path": "created_at", "op": "gte", "value": "-7d" },
      { "path": "type", "op": "eq", "value": "meeting" }
    ]
  },
  "include": ["persons"],
  "orderBy": [{ "field": "created_at", "direction": "desc" }],
  "limit": 50
}
```

## Best Practices

1. **Start with dry-run** for complex queries to see API call estimates
2. **Use limit** to avoid fetching too much data
3. **Be specific with where** to reduce client-side filtering
4. **Avoid deep includes** which cause N+1 API calls
5. **Include `$version`** in saved query files for forward compatibility

## Limitations

- All filtering except listEntries field filters happens client-side
- Includes cause N+1 API calls (1 per parent record)
- Maximum 10,000 records per query for safety
- No cross-entity joins (use includes instead)
