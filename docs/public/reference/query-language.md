# Query Language Reference

This document provides a complete reference for the Affinity CLI query language.

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

| Entity | Description | Service |
|--------|-------------|---------|
| `persons` | People in CRM | PersonService |
| `companies` | Companies/organizations | CompanyService |
| `opportunities` | Deals/opportunities | OpportunityService |
| `listEntries` | Entries in Affinity lists | ListEntryService |
| `interactions` | Emails, calls, meetings | InteractionService |
| `notes` | Notes on entities | NoteService |

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
  "and_": [
    { "path": "status", "op": "eq", "value": "Active" },
    { "path": "amount", "op": "gt", "value": 10000 }
  ]
}
```

#### OR

```json
{
  "or_": [
    { "path": "email", "op": "contains", "value": "@acme.com" },
    { "path": "email", "op": "contains", "value": "@acme.io" }
  ]
}
```

#### NOT

```json
{
  "not_": { "path": "status", "op": "eq", "value": "Closed" }
}
```

### Quantifiers

#### ALL

All items in collection must match:

```json
{
  "all_": {
    "over": "tags",
    "where": { "path": ".", "op": "starts_with", "value": "priority" }
  }
}
```

#### NONE

No items in collection may match:

```json
{
  "none_": {
    "over": "tags",
    "where": { "path": ".", "op": "eq", "value": "spam" }
  }
}
```

### EXISTS Subquery

```json
{
  "exists_": {
    "from": "interactions",
    "where": {
      "and_": [
        { "path": "person_id", "op": "eq", "value": { "$ref": "id" } },
        { "path": "type", "op": "eq", "value": "meeting" }
      ]
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
    "and_": [
      { "path": "count", "op": "gte", "value": 5 },
      { "path": "total", "op": "gt", "value": 100000 }
    ]
  }
}
```

## Include Relationships

### Available Relationships

**From `persons`:**
- `companies` - Associated companies
- `opportunities` - Associated opportunities
- `interactions` - Interactions involving person
- `notes` - Notes on person

**From `companies`:**
- `persons` - Associated people
- `opportunities` - Associated opportunities
- `interactions` - Interactions involving company
- `notes` - Notes on company

**From `opportunities`:**
- `persons` - Associated people
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
