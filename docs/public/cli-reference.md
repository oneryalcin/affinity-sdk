# CLI JSON Output Reference

This document describes the structure of JSON output from Affinity CLI commands.

## Table of Contents

- [Standard Response Format](#standard-response-format)
- [Resolved Metadata](#resolved-metadata)
- [Pagination Metadata](#pagination-metadata)
- [Rate Limit Metadata](#rate-limit-metadata)
- [Error Responses](#error-responses)

## Standard Response Format

All CLI commands support the `--json` flag for machine-readable output. The response follows a consistent structure:

```json
{
  "ok": true,
  "command": "person get",
  "data": {
    "person": {
      "id": 12345,
      "firstName": "John",
      "lastName": "Doe",
      "emailAddresses": ["john@example.com"]
    }
  },
  "meta": {
    "durationMs": 234,
    "resolved": {},
    "pagination": null,
    "rateLimit": {
      "limit": 300,
      "remaining": 299,
      "reset": 1609459200
    }
  }
}
```

### Top-Level Fields

- **ok** (boolean): `true` if the command succeeded, `false` if it failed
- **command** (string): The command that was executed (e.g., `"person get"`)
- **data** (object): The command's result data (structure varies by command)
- **meta** (object): Metadata about the command execution

### Meta Object

The `meta` object contains:

- **durationMs** (number): How long the command took to execute (in milliseconds)
- **resolved** (object): Information about how CLI inputs were resolved to API parameters
- **pagination** (object | null): Pagination metadata for list commands
- **rateLimit** (object): API rate limit information

## Resolved Metadata

The `meta.resolved` field contains information about how CLI inputs were resolved to API parameters. The structure varies by command type based on what inputs need resolution.

### Entity Commands

For person, company, and opportunity commands, the resolved metadata includes information about how entity selectors were resolved:

```json
{
  "resolved": {
    "person": {
      "input": "john@example.com",
      "personId": 12345,
      "source": "email",
      "canonicalUrl": "https://app.affinity.co/persons/12345"
    },
    "fieldSelection": {
      "fieldIds": ["field-123", "field-456"],
      "fieldTypes": ["global"]
    },
    "expand": ["lists", "interactions"]
  }
}
```

#### Entity Selector Resolution

The entity object (e.g., `person`, `company`, `opportunity`) contains:

- **input** (string): The original selector you provided
- **{entityType}Id** (number): The resolved entity ID
- **source** (string): How the selector was resolved
  - `"id"`: Direct numeric ID
  - `"url"`: Affinity URL
  - `"email"`: Email address (persons only)
  - `"name"`: Name search (persons only)
  - `"domain"`: Domain search (companies only)
- **canonicalUrl** (string, optional): The canonical Affinity URL for the entity

#### Field Selection

When field selection options are used (e.g., `--field-id`, `--field-type`), the `fieldSelection` object contains:

- **fieldIds** (array of strings): Specific field IDs requested
- **fieldTypes** (array of strings): Field types requested (e.g., `"global"`, `"list-specific"`)

#### Expansion

When `--expand` is used, the `expand` array contains the expansions requested (e.g., `["lists", "interactions"]`).

### List Commands

For list-related commands, the resolved metadata includes list and saved view resolution:

```json
{
  "resolved": {
    "list": {
      "input": "Sales Pipeline",
      "listId": 789,
      "source": "name"
    },
    "savedView": {
      "input": "My Active Deals",
      "savedViewId": 456,
      "name": "My Active Deals"
    }
  }
}
```

#### List Resolution

The `list` object contains:

- **input** (string): The original list selector
- **listId** (number): The resolved list ID
- **source** (string): How the list was resolved (`"id"`, `"url"`, or `"name"`)

#### Saved View Resolution

When a saved view is specified, the `savedView` object contains:

- **input** (string): The original saved view selector
- **savedViewId** (number): The resolved saved view ID
- **name** (string): The name of the saved view

### Opportunity Commands

Opportunity commands may include additional resolution metadata:

```json
{
  "resolved": {
    "opportunity": {
      "input": "OPP-123",
      "opportunityId": 12345,
      "source": "id"
    },
    "list": {
      "input": "789",
      "listId": 789,
      "source": "id"
    }
  }
}
```

## Pagination Metadata

For commands that return collections, pagination metadata is namespaced by collection type:

```json
{
  "data": {
    "persons": [
      {"id": 1, "firstName": "Alice"},
      {"id": 2, "firstName": "Bob"}
    ]
  },
  "meta": {
    "pagination": {
      "persons": {
        "nextCursor": "eyJpZCI6MTIzfQ==",
        "prevCursor": null
      }
    }
  }
}
```

### Pagination Object Structure

The pagination key always matches the data key (`persons`, `companies`, `opportunities`, `rows`, etc.). Each pagination object contains:

- **nextCursor** (string | null): Cursor for the next page, or `null` if this is the last page
- **prevCursor** (string | null): Cursor for the previous page, or `null` if this is the first page

### Using Pagination Cursors

To fetch the next page, use the `--cursor` option:

```bash
affinity person search "Alice" --json
# Get nextCursor from response
affinity person search "Alice" --cursor "eyJpZCI6MTIzfQ==" --json
```

## Rate Limit Metadata

All API responses include rate limit information:

```json
{
  "meta": {
    "rateLimit": {
      "limit": 300,
      "remaining": 299,
      "reset": 1609459200
    }
  }
}
```

### Rate Limit Fields

- **limit** (number): Total number of requests allowed per time window
- **remaining** (number): Number of requests remaining in the current window
- **reset** (number): Unix timestamp when the rate limit window resets

## Error Responses

When a command fails, the response structure changes:

```json
{
  "ok": false,
  "command": "person get",
  "error": {
    "type": "api_error",
    "message": "Person not found",
    "statusCode": 404,
    "details": {
      "personId": 99999
    }
  },
  "meta": {
    "durationMs": 123
  }
}
```

### Error Object

The `error` object contains:

- **type** (string): Error category
  - `"api_error"`: API returned an error
  - `"usage_error"`: Invalid command usage
  - `"validation_error"`: Input validation failed
  - `"network_error"`: Network/connection issue
- **message** (string): Human-readable error description
- **statusCode** (number, optional): HTTP status code for API errors
- **details** (object, optional): Additional error context

## Examples

### Person Get by Email

Command:
```bash
affinity person get email:john@example.com --json
```

Response:
```json
{
  "ok": true,
  "command": "person get",
  "data": {
    "person": {
      "id": 12345,
      "firstName": "John",
      "lastName": "Doe",
      "emailAddresses": ["john@example.com"]
    }
  },
  "meta": {
    "durationMs": 156,
    "resolved": {
      "person": {
        "input": "email:john@example.com",
        "personId": 12345,
        "source": "email",
        "canonicalUrl": "https://app.affinity.co/persons/12345"
      }
    },
    "pagination": null,
    "rateLimit": {
      "limit": 300,
      "remaining": 298,
      "reset": 1609459200
    }
  }
}
```

### Person Search with Pagination

Command:
```bash
affinity person search "Alice" --json
```

Response:
```json
{
  "ok": true,
  "command": "person search",
  "data": {
    "persons": [
      {
        "id": 1,
        "firstName": "Alice",
        "lastName": "Smith",
        "emailAddresses": ["alice@example.com"]
      },
      {
        "id": 2,
        "firstName": "Alice",
        "lastName": "Jones",
        "emailAddresses": ["ajones@example.com"]
      }
    ]
  },
  "meta": {
    "durationMs": 234,
    "resolved": {},
    "pagination": {
      "persons": {
        "nextCursor": "eyJpZCI6Mn0=",
        "prevCursor": null
      }
    },
    "rateLimit": {
      "limit": 300,
      "remaining": 297,
      "reset": 1609459200
    }
  }
}
```

### List Rows with Saved View

Command:
```bash
affinity list rows "Sales Pipeline" --saved-view "Active Deals" --json
```

Response:
```json
{
  "ok": true,
  "command": "list rows",
  "data": {
    "rows": [
      {
        "id": 101,
        "listId": 789,
        "entityId": 12345
      }
    ]
  },
  "meta": {
    "durationMs": 189,
    "resolved": {
      "list": {
        "input": "Sales Pipeline",
        "listId": 789,
        "source": "name"
      },
      "savedView": {
        "input": "Active Deals",
        "savedViewId": 456,
        "name": "Active Deals"
      }
    },
    "pagination": {
      "rows": {
        "nextCursor": null,
        "prevCursor": null
      }
    },
    "rateLimit": {
      "limit": 300,
      "remaining": 296,
      "reset": 1609459200
    }
  }
}
```

## Field Naming Conventions

All field names in JSON output use camelCase to match the Affinity API conventions:

- `firstName` (not `first_name`)
- `emailAddresses` (not `email_addresses`)
- `nextCursor` (not `next_cursor`)

This applies to both the `data` section and all metadata fields.

## JSON Output vs Table Output

Important differences between `--json` and table output:

1. **Completeness**: JSON output includes all fields from the API response, while table output may filter or format fields for readability
2. **Filter Flags**: Flags like `--list-entry-field` and `--field` that control table formatting are ignored in JSON mode
3. **Consistency**: JSON structure is stable and suitable for programmatic parsing
4. **Metadata**: JSON includes full metadata (resolved, pagination, rate limits) that isn't shown in tables

When writing scripts or integrations, always use `--json` for reliable, complete output.

## TypeScript Type Definitions

For TypeScript users, here are type definitions for the CLI output structure:

```typescript
// Standard response wrapper
interface CLIResponse<T = unknown> {
  ok: boolean;
  command: string;
  data?: T;
  error?: CLIError;
  meta: CLIMeta;
}

// Error object (when ok = false)
interface CLIError {
  type: 'api_error' | 'usage_error' | 'validation_error' | 'network_error';
  message: string;
  statusCode?: number;
  details?: Record<string, unknown>;
}

// Metadata object
interface CLIMeta {
  durationMs: number;
  resolved: ResolvedMetadata;
  pagination: PaginationMetadata | null;
  rateLimit: RateLimitInfo;
}

// Resolved metadata (structure varies by command)
interface ResolvedMetadata {
  person?: EntityResolution;
  company?: EntityResolution;
  opportunity?: EntityResolution;
  list?: ListResolution;
  savedView?: SavedViewResolution;
  fieldSelection?: FieldSelection;
  expand?: string[];
}

interface EntityResolution {
  input: string;
  personId?: number;
  companyId?: number;
  opportunityId?: number;
  source: 'id' | 'url' | 'email' | 'name' | 'domain';
  canonicalUrl?: string;
}

interface ListResolution {
  input: string;
  listId: number;
  source: 'id' | 'url' | 'name';
}

interface SavedViewResolution {
  input: string;
  savedViewId: number;
  name: string;
}

interface FieldSelection {
  fieldIds?: string[];
  fieldTypes?: string[];
}

// Pagination (key matches data collection name)
type PaginationMetadata = {
  [collectionName: string]: {
    nextCursor: string | null;
    prevCursor: string | null;
  };
};

// Rate limit info
interface RateLimitInfo {
  limit: number;
  remaining: number;
  reset: number;
}

// Example usage:
interface PersonGetResponse extends CLIResponse<{ person: Person }> {
  data: {
    person: Person;
  };
}

interface PersonSearchResponse extends CLIResponse<{ persons: Person[] }> {
  data: {
    persons: Person[];
  };
}
```

## Related Documentation

- [CLI Commands Reference](cli/commands.md) - Complete command documentation
- [CLI Scripting Guide](cli/scripting.md) - Working with JSON output and pagination
- [CSV Export Guide](guides/csv-export.md) - Exporting data to CSV files
