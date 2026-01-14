# Query Language Reference

This document provides a complete reference for the Affinity CLI query language.

## Quick Start

```json
// Simplest query - get 10 persons
{"from": "persons", "limit": 10}

// Add a filter
{"from": "persons", "where": {"path": "email", "op": "contains", "value": "@acme.com"}, "limit": 10}

// Include related companies
{"from": "persons", "include": ["companies"], "limit": 10}
```

Run with:
```bash
xaffinity query --query '{"from": "persons", "limit": 10}'
```

## Query Object

```json
{
  "$version": "1.0",
  "from": "persons",
  "select": ["id", "firstName", "lastName"],
  "where": { ... },
  "include": ["companies"],
  "orderBy": [{ "field": "lastName", "direction": "asc" }],
  "groupBy": "status",
  "aggregate": { ... },
  "having": { ... },
  "limit": 100
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `$version` | string | No | Query format version (default: `"1.0"`) |
| `from` | string | **Yes** | Entity type to query |
| `select` | string[] | No | Fields to return (default: all) |
| `where` | WhereClause | No | Filter conditions |
| `include` | string[] | No | Related entities to fetch |
| `orderBy` | OrderByClause[] | No | Sort order |
| `groupBy` | string | No | Field to group by |
| `aggregate` | AggregateMap | No | Aggregate functions |
| `having` | HavingClause | No | Filter on aggregates |
| `limit` | integer | No | Maximum records |
| `cursor` | string | No | Pagination cursor |

## Entity Types

| Entity | Description | Service | Query Type |
|--------|-------------|---------|------------|
| `persons` | People in CRM | PersonService | Direct |
| `companies` | Companies/organizations | CompanyService | Direct |
| `opportunities` | Deals/opportunities | OpportunityService | Direct |
| `lists` | Affinity list definitions | ListService | Direct |
| `listEntries` | Entries in Affinity lists | ListEntryService | Requires parent filter |
| `interactions` | Emails, calls, meetings | InteractionService | Include only |
| `notes` | Notes on entities | NoteService | Include only |

### Query Type Details

**Direct** - Can be queried without any required filters:
```json
{"from": "persons", "limit": 10}
```

**Requires parent filter** - Must specify parent context:
```json
{
  "from": "listEntries",
  "where": {"path": "listId", "op": "eq", "value": 12345}
}
```

The `listEntries` entity supports:
- `listId` filter with `eq` or `in` operator
- `listName` filter (resolved to `listId` automatically)
- Multiple lists via `in` operator or `or` conditions
- `fields.*` paths with human-readable field names (resolved to field IDs automatically)

**Include only** - Cannot be queried directly; use as relationship include:
```json
{
  "from": "persons",
  "include": ["interactions", "notes"]
}
```

Direct queries for include-only entities will fail with helpful guidance:
```
QueryParseError: 'interactions' cannot be queried directly.
Use it as an 'include' on a parent entity instead.
Example: {"from": "persons", "include": ["interactions"]}
```

## WHERE Clause

### Simple Condition

```json
{
  "path": "email",
  "op": "contains",
  "value": "@acme.com"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | string | Yes* | Field path (dot notation) |
| `op` | string | Yes | Comparison operator |
| `value` | any | Depends | Comparison value |

*Either `path` or `expr` is required.

### Operators

#### Comparison

| Operator | Description | Value Type |
|----------|-------------|------------|
| `eq` | Equal | any |
| `neq` | Not equal | any |
| `gt` | Greater than | number, date |
| `gte` | Greater or equal | number, date |
| `lt` | Less than | number, date |
| `lte` | Less or equal | number, date |

#### String

| Operator | Description | Value Type |
|----------|-------------|------------|
| `contains` | Contains substring | string |
| `starts_with` | Starts with prefix | string |

#### Collection

| Operator | Description | Value Type |
|----------|-------------|------------|
| `in` | Value in list | array |
| `between` | Value in range | [min, max] |
| `contains_any` | Array has any of | array |
| `contains_all` | Array has all of | array |

#### Null

| Operator | Description | Value |
|----------|-------------|-------|
| `is_null` | Field is null | (none) |
| `is_not_null` | Field is not null | (none) |

### Compound Conditions

#### AND

```json
{
  "and": [
    { "path": "status", "op": "eq", "value": "Active" },
    { "path": "amount", "op": "gt", "value": 10000 }
  ]
}
```

#### OR

```json
{
  "or": [
    { "path": "email", "op": "contains", "value": "@acme.com" },
    { "path": "email", "op": "contains", "value": "@acme.io" }
  ]
}
```

#### NOT

```json
{
  "not": { "path": "status", "op": "eq", "value": "Closed" }
}
```

### Quantifiers

Quantifiers filter records based on related entities. They require fetching relationship data (N+1 API calls).

#### ALL

All related items must match the condition:

```json
{
  "from": "persons",
  "where": {
    "all": {
      "path": "companies",
      "where": { "path": "domain", "op": "contains", "value": ".com" }
    }
  }
}
```

#### NONE

No related items may match the condition:

```json
{
  "from": "persons",
  "where": {
    "none": {
      "path": "companies",
      "where": { "path": "name", "op": "contains", "value": "Competitor" }
    }
  }
}
```

#### COUNT

Count related items using the `_count` pseudo-field:

```json
{
  "from": "persons",
  "where": { "path": "companies._count", "op": "gte", "value": 2 }
}
```

### EXISTS Subquery

Check if related items exist (optionally matching a filter):

```json
{
  "from": "persons",
  "where": {
    "exists": {
      "from": "interactions",
      "where": { "path": "type", "op": "eq", "value": "meeting" }
    }
  }
}
```

## Field Paths

### Dot Notation

```
email                    # Top-level field
fields.Status            # Nested field
company.name             # Related entity field (with include)
```

### Array Access

```
emails[0]                # First element
phones[-1]               # Last element
```

### Escaping

```
fields["Field.With.Dots"]
fields["Field With Spaces"]
```

### Field Name Resolution

For `listEntries` queries, `fields.*` paths support human-readable field names:

```json
{"path": "fields.Status", "op": "eq", "value": "Active"}
```

Field names are resolved case-insensitively against the list's field definitions. If a name is not found, it passes through unchanged (allowing direct use of field IDs like `fields.12345` or `fields.field-260415`).

### Discovering Available Fields

Use the CLI to see what fields are available on each entity:

```bash
# See person fields
xaffinity person get <id> --json | jq 'keys'

# See company fields
xaffinity company get <id> --json | jq 'keys'

# See list entry fields (including custom fields)
xaffinity list entry ls --list-id <id> --limit 1 --json | jq '.[0] | keys'

# See custom list field definitions
xaffinity list field ls --list-id <id>
```

Use the discovered field names in your queries with `fields.<FieldName>` paths.

## Date Values

### Relative Dates

| Format | Meaning |
|--------|---------|
| `-Nd` | N days ago |
| `+Nd` | N days from now |
| `today` | Start of today (00:00:00) |
| `now` | Current timestamp |
| `yesterday` | Start of yesterday |
| `tomorrow` | Start of tomorrow |

### ISO 8601

```
2024-01-15
2024-01-15T10:30:00Z
2024-01-15T10:30:00-05:00
```

## ORDER BY Clause

```json
{
  "orderBy": [
    { "field": "lastName", "direction": "asc" },
    { "field": "firstName", "direction": "asc" }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `field` | string | Yes | Field path |
| `direction` | string | No | `asc` (default) or `desc` |

## Aggregate Functions

### Basic Aggregates

```json
{
  "aggregate": {
    "total": { "count": true },
    "countField": { "count": "email" },
    "totalAmount": { "sum": "amount" },
    "avgAmount": { "avg": "amount" },
    "minAmount": { "min": "amount" },
    "maxAmount": { "max": "amount" }
  }
}
```

| Function | Description |
|----------|-------------|
| `count: true` | Count all records |
| `count: "field"` | Count non-null values |
| `sum: "field"` | Sum numeric field |
| `avg: "field"` | Average numeric field |
| `min: "field"` | Minimum value |
| `max: "field"` | Maximum value |

### Percentile

```json
{
  "aggregate": {
    "p50": { "percentile": { "field": "amount", "p": 50 } },
    "p90": { "percentile": { "field": "amount", "p": 90 } }
  }
}
```

### First/Last

```json
{
  "aggregate": {
    "firstDate": { "first": "created_at" },
    "latestDate": { "last": "created_at" }
  }
}
```

### Expression Aggregates

```json
{
  "aggregate": {
    "total": { "sum": "amount" },
    "count": { "count": true },
    "average": { "divide": ["total", "count"] },
    "adjusted": { "multiply": ["average", 1.1] },
    "withBonus": { "add": ["total", 1000] },
    "discounted": { "subtract": ["total", 500] }
  }
}
```

## HAVING Clause

Filter groups by aggregate values:

```json
{
  "groupBy": "status",
  "aggregate": {
    "count": { "count": true },
    "total": { "sum": "amount" }
  },
  "having": {
    "and": [
      { "path": "count", "op": "gte", "value": 5 },
      { "path": "total", "op": "gt", "value": 100000 }
    ]
  }
}
```

## Include vs Quantifiers

Both `include` and quantifiers fetch relationship data, but serve different purposes:

| Feature | `include` | Quantifiers (`all`, `none`, `exists`, `_count`) |
|---------|-----------|------------------------------------------------|
| Purpose | Get related data in response | Filter based on related data |
| Output | Related records in result | Only affects which records match |
| Use case | "Show me persons WITH their companies" | "Show me persons WHO HAVE 2+ companies" |

### Examples

```json
// Include: Get persons and their companies
{"from": "persons", "include": ["companies"], "limit": 10}
// Result: [{"id": 1, "firstName": "John", "companies": [{"id": 100, "name": "Acme"}]}]

// Quantifier: Get persons who have 2+ companies (companies not in result)
{"from": "persons", "where": {"path": "companies._count", "op": "gte", "value": 2}, "limit": 10}
// Result: [{"id": 1, "firstName": "John"}]

// Both: Get persons with 2+ companies AND include those companies
{"from": "persons", "where": {"path": "companies._count", "op": "gte", "value": 2}, "include": ["companies"], "limit": 10}
```

## Include Relationships

### Available Relationships

**From `persons`:**
- `companies` - Associated companies
- `opportunities` - Associated opportunities
- `interactions` - Interactions involving person
- `notes` - Notes on person

**From `companies`:**
- `persons` - Associated persons
- `opportunities` - Associated opportunities
- `interactions` - Interactions involving company
- `notes` - Notes on company

**From `opportunities`:**
- `persons` - Associated persons
- `companies` - Associated companies
- `interactions` - Interactions on opportunity
- `notes` - Notes on opportunity

### Include Syntax

```json
{
  "from": "persons",
  "include": ["companies", "opportunities"]
}
```

Included data appears in results:

```json
{
  "data": [
    {
      "id": 123,
      "firstName": "John",
      "companies": [
        { "id": 456, "name": "Acme Inc" }
      ],
      "opportunities": []
    }
  ]
}
```

## Error Responses

### Parse Error

```json
{
  "error": "QueryParseError",
  "message": "Unknown operator 'like'. Supported: eq, neq, gt, gte, lt, lte, contains, starts_with, in, between, is_null, is_not_null",
  "field": "where.op"
}
```

### Validation Error

```json
{
  "error": "QueryValidationError",
  "message": "Cannot use 'aggregate' with 'include'. Aggregates collapse records.",
  "field": "aggregate"
}
```

### Execution Error

```json
{
  "error": "QueryExecutionError",
  "message": "Failed to fetch persons: API rate limit exceeded"
}
```

## Version History

| Version | Status | Changes |
|---------|--------|---------|
| `1.0` | Current | Initial release with full query language |

## Constraints

- `aggregate` and `include` cannot be used together
- `groupBy` requires `aggregate`
- `having` requires `aggregate`
- `limit` must be non-negative
- Maximum 10,000 records per query

## Performance Considerations

### Decision Tree for Quantifier Queries

```
Do you need all, none, exists, or _count?
├── No → Use normal filters (fast, no N+1 calls)
└── Yes → What entity are you querying from?
    ├── listEntries → Safe (bounded by list size)
    └── persons/companies/opportunities → ⚠️ Read below
        ├── Add cheap pre-filters first to reduce dataset
        ├── Use --max-records 100 for exploration
        └── Use --dry-run to preview API calls
```

### Quantifier Queries on Large Databases

The `all`, `none`, `exists`, and `_count` operators require fetching
relationship data for each record. This causes N+1 API calls, which can
be very slow on large databases.

| Database Size | N+1 API Calls | Time @ 30 req/s | Verdict |
|---------------|---------------|-----------------|---------|
| 100 records | 100 | ~3 seconds | ✅ Usable |
| 1,000 records | 1,000 | ~33 seconds | ⚠️ Slow |
| 10,000 records | 10,000 | ~5.5 minutes | ❌ Painful |

**Important**: Unbounded queries (from `persons`, `companies`, or `opportunities`)
with quantifier filters require explicit `--max-records` to prevent accidentally
running very long queries.

### Recommended Patterns

1. **Start from listEntries** (bounded by list size):
   ```json
   {
     "from": "listEntries",
     "where": {
       "and": [
         {"path": "listId", "op": "eq", "value": 12345},
         {"path": "entity.companies._count", "op": "gte", "value": 2}
       ]
     }
   }
   ```

2. **Add pre-filters** to reduce dataset first:
   ```json
   {
     "from": "companies",
     "where": {
       "and": [
         {"path": "domain", "op": "contains", "value": "example"},
         {"path": "persons._count", "op": "gte", "value": 2}
       ]
     },
     "limit": 10
   }
   ```
   Then run with: `xaffinity query --file query.json --max-records 100`

3. **Use --max-records** for exploration:
   ```bash
   xaffinity query --query '...' --max-records 100
   ```

### Lazy Loading Optimization

When a query has both cheap filters (local field comparisons) and expensive
filters (quantifiers), the engine automatically applies cheap filters first
to reduce the dataset before making N+1 API calls. This can dramatically
reduce execution time.

### Using Dry-Run

Always preview expensive queries with `--dry-run`:

```bash
xaffinity query --file query.json --dry-run
```

The dry-run output shows:
- Estimated API calls (or "UNBOUNDED" for unbounded quantifier queries)
- Whether `--max-records` is required
- Lazy loading optimization status
