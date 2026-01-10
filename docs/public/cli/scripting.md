# Scripting

## Session caching for pipelines

When running multiple CLI commands in a pipeline, enable session caching to avoid redundant API calls:

```bash
#!/bin/bash
export AFFINITY_SESSION_CACHE=$(xaffinity session start) || exit 1
trap 'xaffinity session end; unset AFFINITY_SESSION_CACHE' EXIT

# Commands share cached metadata (field definitions, list resolution)
xaffinity list export "My List" | xaffinity person get
```

See [Pipeline Optimization](commands.md#pipeline-optimization) for details.

## JSON output

Use `--json` for machine-readable output:

```bash
xaffinity whoami --json | jq
```

## Timezone-safe datetime handling

Date/time flags (`--after`, `--before`, etc.) interpret naive strings as **local time**. For reproducible scripts across timezones, always use explicit UTC:

```bash
# Use Z suffix for explicit UTC
xaffinity interaction ls --type meeting --person-id 123 --after 2024-01-01T00:00:00Z --json

# Or use explicit timezone offset
xaffinity interaction ls --type meeting --person-id 123 --after 2024-01-01T00:00:00-05:00 --json

# Or use --days for relative date ranges
xaffinity interaction ls --type meeting --person-id 123 --days 30 --json
```

JSON output always returns datetimes in UTC (with `+00:00` suffix). See the [Datetime Handling Guide](../guides/datetime-handling.md) for full details on SDK vs CLI behavior.

**Note:** `interaction ls` auto-chunks date ranges > 1 year into API-compatible segments. For multi-year queries, dates are split transparently.

## Pagination and resume

Some commands include resume tokens in `meta.pagination`.

- `meta.pagination` is keyed by section name.
- Resume cursor: `meta.pagination.<section>.nextCursor` (resume with `--cursor <cursor>`)
- Treat cursors as opaque strings (some may look like URLs); don't parse them.

**Note:** `interaction ls` does not use pagination cursors. Instead, it auto-fetches all results within the specified date range, chunking as needed for ranges > 1 year.

Example (person list with query):

```bash
xaffinity person ls --query "alice" --json | jq -r '.meta.pagination.persons.nextCursor'
xaffinity person ls --query "alice" --cursor "$CURSOR" --json
```

Example (list inventory):

```bash
xaffinity list ls --json | jq -r '.meta.pagination.lists.nextCursor'
xaffinity list ls --cursor "$CURSOR" --json
```

Note: if you use `--max-results` and it truncates results mid-page, the CLI may omit pagination to avoid producing an unsafe resume token.

## CSV Output

The `--csv` flag outputs CSV to stdout, making it composable with UNIX tools:

```bash
# Save to file
xaffinity list export 123 --csv > out.csv

# Pipe to other tools
xaffinity person ls --all --csv | wc -l
xaffinity list export 123 --csv | head -10
```

**Note:** `--csv` and `--json` are mutually exclusive. Use one or the other.

## Machine-Readable Help

Use `--help --json` to get machine-readable command documentation. This is useful for:

- Building automation tools that discover CLI capabilities
- Generating command registries for AI integrations (like MCP servers)
- Validating command arguments programmatically

```bash
xaffinity --help --json
```

### Output Format

```json
{
  "commands": [
    {
      "name": "person create",
      "description": "Create a person.",
      "category": "write",
      "destructive": false,
      "parameters": {
        "--first-name": {"type": "string", "required": false},
        "--last-name": {"type": "string", "required": false},
        "--email": {"type": "string", "required": false, "multiple": true}
      },
      "positionals": []
    },
    {
      "name": "person delete",
      "description": "Delete a person.",
      "category": "write",
      "destructive": true,
      "parameters": {
        "--yes": {"type": "flag", "required": false}
      },
      "positionals": [
        {"name": "PERSON_ID", "type": "int", "required": true}
      ]
    }
  ]
}
```

### Command Metadata

| Field | Description |
|-------|-------------|
| `name` | Full command path (e.g., `"person create"`, `"list entry add"`) |
| `description` | Human-readable description |
| `category` | `"read"`, `"write"`, or `"local"` (no-network) |
| `destructive` | `true` for delete commands |
| `parameters` | Named options with type info |
| `positionals` | Positional arguments with type info |

### Parameter Types

| Type | Description |
|------|-------------|
| `string` | Text value |
| `int` | Integer value |
| `flag` | Boolean flag (no value) |
| `choice` | One of allowed values (see `choices` array) |

Parameters with `"multiple": true` can be specified multiple times.
