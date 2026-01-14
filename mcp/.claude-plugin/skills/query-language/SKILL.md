---
name: query-language
description: Use when user needs complex data queries, multi-entity joins, aggregations, or analysis across Affinity data. Also use when user wants to filter, group, sort, or aggregate CRM records programmatically. Triggers: "query language", "structured query", "SQL-like", "find all persons where", "count opportunities by", "sum deal values", "average amount", "group by status", "filter AND/OR", "include companies with persons".
---

# Affinity Query Language

This skill covers the structured query language for querying Affinity CRM data via the `query` MCP tool.

## When to Use This Tool

Use the `query` tool instead of individual CLI commands when you need:
- **Complex filtering** with multiple conditions (AND, OR, NOT)
- **Include relationships** (e.g., get persons with their companies)
- **Aggregations** (count, sum, avg, min, max, percentile)
- **Grouping** (count opportunities by status)
- **Multi-field sorting**
- **Batch analysis** across large datasets

For simple lookups, prefer `execute-read-command` with individual commands.

## Quick Start

```json
// Simplest query - get 10 persons
{"from": "persons", "limit": 10}

// Add a filter
{"from": "persons", "where": {"path": "email", "op": "contains", "value": "@acme.com"}, "limit": 10}

// Include related companies
{"from": "persons", "include": ["companies"], "limit": 10}

// Query list entries
{"from": "listEntries", "where": {"path": "listName", "op": "eq", "value": "Dealflow"}, "limit": 10}
```

## Query Structure

```json
{
  "$version": "1.0",
  "from": "persons",
  "where": { "path": "email", "op": "contains", "value": "@acme.com" },
  "include": ["companies", "opportunities"],
  "select": ["id", "firstName", "lastName", "email"],
  "orderBy": [{ "field": "lastName", "direction": "asc" }],
  "limit": 100
}
```

### Required Fields

| Field | Description |
|-------|-------------|
| `from` | Entity type: `persons`, `companies`, `opportunities`, `listEntries`, `interactions`, `notes` |

### Optional Fields

| Field | Description |
|-------|-------------|
| `$version` | Query format version (default: "1.0") |
| `where` | Filter conditions |
| `include` | Related entities to fetch |
| `select` | Fields to return (default: all) |
| `orderBy` | Sort order |
| `groupBy` | Field to group by (requires `aggregate`) |
| `aggregate` | Aggregate functions to compute |
| `having` | Filter on aggregate results |
| `limit` | Maximum records to return |

## Filter Operators

### Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equal | `{"path": "status", "op": "eq", "value": "Active"}` |
| `neq` | Not equal | `{"path": "status", "op": "neq", "value": "Closed"}` |
| `gt` | Greater than | `{"path": "amount", "op": "gt", "value": 10000}` |
| `gte` | Greater than or equal | `{"path": "amount", "op": "gte", "value": 10000}` |
| `lt` | Less than | `{"path": "amount", "op": "lt", "value": 5000}` |
| `lte` | Less than or equal | `{"path": "amount", "op": "lte", "value": 5000}` |

### String Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `contains` | Contains substring (case-insensitive) | `{"path": "email", "op": "contains", "value": "@gmail"}` |
| `starts_with` | Starts with (case-insensitive) | `{"path": "name", "op": "starts_with", "value": "Acme"}` |
| `ends_with` | Ends with (case-insensitive) | `{"path": "email", "op": "ends_with", "value": "@acme.com"}` |

### Collection Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `in` | Value in list | `{"path": "status", "op": "in", "value": ["New", "Active"]}` |
| `between` | Value in range | `{"path": "amount", "op": "between", "value": [1000, 5000]}` |
| `contains_any` | String contains any substring (case-insensitive) | `{"path": "bio", "op": "contains_any", "value": ["python", "java"]}` |
| `contains_all` | String contains all substrings (case-insensitive) | `{"path": "bio", "op": "contains_all", "value": ["senior", "engineer"]}` |
| `has_any` | Array field contains any of the values | `{"path": "fields.Team Member", "op": "has_any", "value": ["LB", "MA"]}` |
| `has_all` | Array field contains all of the values | `{"path": "fields.Team Member", "op": "has_all", "value": ["LB", "MA"]}` |

### Multi-Select Field Filtering

Multi-select dropdown fields (like "Team Member") return arrays from the API. The `eq` and `neq` operators handle these automatically:

| Operator | Single-value field | Multi-select field |
|----------|-------------------|-------------------|
| `eq` | Exact match | Scalar: membership check / List: set equality |
| `neq` | Not equal | Scalar: not in array / List: set inequality |
| `in` | Value in list | Any intersection between arrays |
| `has_any` | Returns false | Any specified value present |
| `has_all` | Returns false | All specified values present |

**Examples:**

```json
// Find entries where Team Member includes "LB"
{ "path": "fields.Team Member", "op": "eq", "value": "LB" }

// Find entries where Team Member includes any of ["LB", "DW"]
{ "path": "fields.Team Member", "op": "has_any", "value": ["LB", "DW"] }

// Find entries where Team Member includes both "LB" and "MA"
{ "path": "fields.Team Member", "op": "has_all", "value": ["LB", "MA"] }
```

### Null/Empty Checks

| Operator | Description | Example |
|----------|-------------|---------|
| `is_null` | Field is null or empty string | `{"path": "email", "op": "is_null"}` |
| `is_not_null` | Field is not null and not empty | `{"path": "email", "op": "is_not_null"}` |
| `is_empty` | Field is null, empty string, or empty array | `{"path": "emails", "op": "is_empty"}` |

## Compound Conditions

### AND

```json
{
  "where": {
    "and": [
      { "path": "status", "op": "eq", "value": "Active" },
      { "path": "amount", "op": "gt", "value": 10000 }
    ]
  }
}
```

### OR

```json
{
  "where": {
    "or": [
      { "path": "email", "op": "contains", "value": "@acme.com" },
      { "path": "email", "op": "contains", "value": "@acme.io" }
    ]
  }
}
```

### NOT

```json
{
  "where": {
    "not": { "path": "status", "op": "eq", "value": "Closed" }
  }
}
```

## Advanced Filtering (Quantifiers, Exists, Count)

Filter based on related entities using quantifiers and existence checks.

> **Include vs Quantifiers:** Use `include` to **get** related data in the response (e.g., `"include": ["companies"]`). Use quantifiers to **filter** by related data (e.g., `{"path": "companies._count", "op": "gte", "value": 2}`). You can use both together.

### ALL Quantifier

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

**Note:** Returns `true` for records with no related items (vacuous truth). To require at least one, combine with `_count`:

```json
{
  "where": {
    "and": [
      { "path": "companies._count", "op": "gte", "value": 1 },
      { "all": { "path": "companies", "where": { "path": "domain", "op": "contains", "value": ".com" }}}
    ]
  }
}
```

### NONE Quantifier

No related items may match the condition:

```json
{
  "from": "persons",
  "where": {
    "none": {
      "path": "interactions",
      "where": { "path": "type", "op": "eq", "value": "spam" }
    }
  }
}
```

### EXISTS Clause

At least one related item exists (optionally matching a filter):

```json
// Simple existence check
{
  "from": "persons",
  "where": { "exists": { "from": "interactions" }}
}

// With filter
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

### Count Pseudo-Field

Count related items and compare:

```json
// Persons with 2 or more companies
{
  "from": "persons",
  "where": { "path": "companies._count", "op": "gte", "value": 2 }
}

// Persons with no interactions
{
  "from": "persons",
  "where": { "path": "interactions._count", "op": "eq", "value": 0 }
}
```

### Available Relationships for Quantifiers

| From Entity | Available Relationship Paths |
|-------------|------------------------------|
| `persons` | `companies`, `opportunities`, `interactions`, `notes`, `listEntries` |
| `companies` | `persons`, `opportunities`, `interactions`, `notes`, `listEntries` |
| `opportunities` | `persons`, `companies`, `interactions` |

### Limitations

- **Nested quantifiers not supported**: Cannot use `all`/`none`/`exists` inside another quantifier
- **N+1 API calls**: Quantifiers fetch relationship data for each record (use dry-run to preview)

## Include Relationships

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
| `persons` | `companies`, `opportunities`, `interactions`, `notes`, `listEntries` |
| `companies` | `persons`, `opportunities`, `interactions`, `notes`, `listEntries` |
| `opportunities` | `persons`, `companies`, `interactions` |
| `lists` | `entries` |
| `listEntries` | `entity` (dynamically resolves to person/company/opportunity based on entityType) |

## Aggregations

### Basic Aggregates

```json
{
  "from": "opportunities",
  "aggregate": {
    "total": { "count": true },
    "totalValue": { "sum": "amount" },
    "avgValue": { "avg": "amount" },
    "minValue": { "min": "amount" },
    "maxValue": { "max": "amount" }
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

### Having (Filter on Aggregates)

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

## Querying List Entries

`listEntries` requires either `listId` or `listName` filter:

```json
// By ID
{"from": "listEntries", "where": {"path": "listId", "op": "eq", "value": 12345}}

// By name (executor resolves name → ID at runtime)
{"from": "listEntries", "where": {"path": "listName", "op": "eq", "value": "Dealflow"}}
```

**Invalid paths:** `list.name`, `list.id` - use `listName` or `listId` directly.

**Note:** When using `listName`, the query executor looks up the list by name and resolves it to a `listId` before fetching entries. This adds one API call but allows using human-readable names.

### Custom Field Values

When querying listEntries with `groupBy`, `aggregate`, or `where` on `fields.*` paths, the query engine automatically detects which fields are referenced and requests their values from the API.

```json
{
  "from": "listEntries",
  "where": {"path": "listName", "op": "eq", "value": "Dealflow"},
  "groupBy": "fields.Status",
  "aggregate": {"count": {"count": true}}
}
```

To select all custom fields, use `fields.*` wildcard in `select`:

```json
{
  "from": "listEntries",
  "where": {"path": "listId", "op": "eq", "value": 12345},
  "select": ["listEntryId", "entityName", "fields.*"],
  "limit": 50
}
```

### Available Select Fields

| Field | Description |
|-------|-------------|
| `listEntryId` | List entry ID (same as `id`) |
| `entityId` | ID of the company/person/opportunity |
| `entityName` | Name of the entity |
| `entityType` | "company", "person", or "opportunity" |
| `listId` | Parent list ID |
| `createdAt` | Entry creation timestamp |
| `fields.<Name>` | Custom field value by name |
| `fields.*` | All custom fields (wildcard) |

## Field Paths

Access nested fields using dot notation:

```json
{
  "from": "listEntries",
  "where": { "path": "fields.Status", "op": "eq", "value": "Active" }
}
```

Common paths:
- `fields.<FieldName>` - Custom list fields on listEntries
- `fields.*` - All custom fields (wildcard, use in `select`)
- `emails[0]` - First email in array
- `company.name` - Nested object field (on included relationships)

## Date Filtering

### Relative Dates

```json
{
  "from": "interactions",
  "where": { "path": "created_at", "op": "gte", "value": "-30d" }
}
```

Supported formats:
- `-30d` - 30 days ago
- `+7d` - 7 days from now
- `today` - Start of today
- `now` - Current time
- `yesterday` - Start of yesterday
- `tomorrow` - Start of tomorrow

## Dry-Run Mode

**Always use dry-run first** to preview expensive queries:

```json
{
  "query": {
    "from": "persons",
    "include": ["companies", "opportunities"]
  },
  "dryRun": true
}
```

Returns execution plan with:
- Estimated API calls
- Estimated records
- Step breakdown
- Warnings about expensive operations

## Examples

### Find VIP Contacts

```json
{
  "from": "persons",
  "where": {
    "and": [
      { "path": "email", "op": "is_not_null" },
      { "path": "fields.VIP", "op": "eq", "value": true }
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

### Recent Interactions

```json
{
  "from": "interactions",
  "where": {
    "and": [
      { "path": "created_at", "op": "gte", "value": "-7d" },
      { "path": "type", "op": "in", "value": ["call", "meeting"] }
    ]
  },
  "include": ["persons"],
  "orderBy": [{ "field": "created_at", "direction": "desc" }],
  "limit": 50
}
```

### Companies Without Recent Activity

```json
{
  "from": "companies",
  "where": {
    "or": [
      { "path": "lastInteraction.date", "op": "lt", "value": "-90d" },
      { "path": "lastInteraction.date", "op": "is_null" }
    ]
  },
  "limit": 100
}
```

## Tool Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | object | required | The JSON query object |
| `dryRun` | boolean | false | Preview execution plan without running |
| `maxRecords` | integer | 1000 | Safety limit (max 10000) |
| `timeout` | integer | 120 | Query timeout in seconds |
| `maxOutputBytes` | integer | 50000 | Truncation limit for results |
| `format` | string | "json" | Output format (see Output Formats below) |

## Output Formats

The `format` parameter controls how results are returned. Choose based on your use case:

| Format | Token Efficiency | Best For | Description |
|--------|-----------------|----------|-------------|
| `json` | Low | Programmatic use | Full JSON structure with `data`, `included`, `pagination` |
| `jsonl` | Medium | Streaming | One JSON object per line (data rows only) |
| `markdown` | Medium-High | **LLM analysis** | GitHub-flavored table (best comprehension) |
| `toon` | **High (~40% fewer)** | Large datasets | Token-Optimized Object Notation |
| `csv` | Medium | Spreadsheets | Comma-separated values |

### Format Recommendations

- **For LLM analysis tasks**: Use `markdown` - LLMs are trained on documentation and tables
- **For large result sets**: Use `toon` to minimize tokens (30-60% smaller than JSON)
- **For programmatic processing**: Use `json` (default) for full structure
- **For streaming workflows**: Use `jsonl` for line-by-line processing

### Format Examples

**JSON (default):**
```json
{"data": [{"id": 1, "name": "Acme"}], "included": {...}, "pagination": {...}}
```

**JSONL:**
```jsonl
{"id": 1, "name": "Acme"}
{"id": 2, "name": "Beta"}
```

**Markdown:**
```markdown
| id | name |
| --- | --- |
| 1 | Acme |
| 2 | Beta |
```

**TOON:**
```
[2]{id,name}:
  1,Acme
  2,Beta
```

**Note:** When using `jsonl`, `markdown`, `toon`, or `csv`, the `included` and `pagination` fields are omitted. Use `json` format if you need related entities or pagination info.

## Best Practices

1. **Start with dry-run** for complex queries to see API call estimates
2. **Use limit** to avoid fetching too much data
3. **Be specific with where** to reduce client-side filtering
4. **Avoid deep includes** which cause N+1 API calls
5. **Use groupBy + aggregate** for reports instead of fetching all records
6. **For quantifier queries** on large databases, always add `maxRecords`

## Quantifier Query Performance

**Quick decision:**
- `listEntries` → Safe (bounded by list size)
- `persons`/`companies`/`opportunities` with quantifiers → Requires `maxRecords`

**Important**: Queries using `all`, `none`, `exists`, or `_count` on unbounded
entities (`persons`, `companies`, `opportunities`) require explicit `maxRecords`.

**Why?** These operations make N+1 API calls (one per record). On a database with
50,000 persons, this could take 26+ minutes.

**Recommended approach:**
1. Start from `listEntries` (bounded by list size) instead of unbounded entities
2. Add cheap pre-filters before quantifier conditions to reduce N+1 calls
3. Use `maxRecords` to explicitly limit scope: `maxRecords: 100`
4. Use `dryRun: true` to preview estimated API calls before running

**Example - safe quantifier query:**
```json
{
  "query": {
    "from": "listEntries",
    "where": {
      "and": [
        {"path": "listName", "op": "eq", "value": "Target Companies"},
        {"path": "persons._count", "op": "gte", "value": 3}
      ]
    }
  },
  "maxRecords": 1000
}
```

## Limitations

- All filtering except `listEntries` field filters happens client-side
- Includes cause N+1 API calls (1 per parent record)
- No cross-entity joins (use includes instead)
- Maximum 10,000 records per query for safety
- Nested quantifiers (`all`/`none`/`exists` inside each other) not supported
- OR clauses containing quantifiers cannot benefit from lazy loading optimization
