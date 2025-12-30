# List Export with Expansions

Export list entries along with their associated entities (people, companies, opportunities).

## Valid Expand Values by List Type

| List Type | Valid `--expand` Values |
|-----------|------------------------|
| opportunity | `people`, `companies` |
| person | `companies`, `opportunities` |
| company | `people`, `opportunities` |

Using an invalid expand value for the list type fails with exit code 2.

## Basic Usage

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

## Controlling Association Limits

By default, up to 100 associations are fetched per entry per expand type.

```bash
# Limit associations per entry (default: 100)
xaffinity list export LIST_ID --expand people --expand-max-results 50 --all --csv output.csv

# Fetch ALL associations (no limit) - use for complete data
xaffinity list export LIST_ID --expand people --expand-all --all --csv output.csv
```

**Note:** `--expand-max-results` applies per expand type per entry. With `--expand people --expand companies --expand-max-results 10`, you get up to 10 people AND up to 10 companies per entry.

## CSV Output Modes

### Flat Mode (default)

One row per association - easier to filter in spreadsheets:

```bash
xaffinity list export LIST_ID --expand people --csv-mode flat --all --csv flat.csv
```

Output:
```csv
listEntryId,entityName,Status,expandedType,expandedId,expandedName,expandedEmail
123,Big Deal,Active,person,789,Alice Smith,alice@example.com
123,Big Deal,Active,person,790,Bob Jones,bob@example.com
123,Big Deal,Active,company,101,Acme Corp,
124,Small Deal,Pending,company,102,Beta Inc,
```

### Nested Mode

One row per entry with JSON arrays in columns:

```bash
xaffinity list export LIST_ID --expand people --csv-mode nested --all --csv nested.csv
```

Output:
```csv
listEntryId,entityName,Status,_expand_people
123,Big Deal,Active,"[{""id"": 789, ""name"": ""Alice Smith""}]"
```

**Warning:** `--expand-all` with `--csv-mode nested` can be memory-intensive for entries with many associations.

## Expanding Entity Fields (Phase 4)

By default, only core fields are included (id, name, email/domain). To include additional fields:

```bash
# Include specific fields on expanded entities
xaffinity list export LIST_ID --expand people \
  --expand-fields "Title" --expand-fields "Department" \
  --all --csv output.csv

# Include all fields of a type (global, enriched, relationship-intelligence)
xaffinity list export LIST_ID --expand people \
  --expand-field-type enriched \
  --all --csv output.csv

# Combine both (union of specified fields and field types)
xaffinity list export LIST_ID --expand people \
  --expand-fields "Custom Status" --expand-field-type enriched \
  --all --csv output.csv
```

## Expanding Opportunities (Phase 5)

For person and company lists, you can expand associated opportunities:

```bash
# Expand opportunities for all people on a person list
xaffinity list export LIST_ID --expand opportunities --all --csv output.csv

# Scope to a specific opportunity list (recommended for performance)
xaffinity list export LIST_ID --expand opportunities \
  --expand-opportunities-list "Pipeline" \
  --all --csv output.csv
```

**Performance Warning:** Without `--expand-opportunities-list`, the CLI searches ALL opportunity lists you have access to. This can be very slow for large workspaces. Always specify `--expand-opportunities-list` when possible.

## Filtering Expanded Associations (Phase 5)

Filter which associations are included based on field values:

```bash
# Only include people named "Alice"
xaffinity list export LIST_ID --expand people \
  --expand-filter "name=Alice" \
  --all --csv output.csv

# Exclude inactive associations
xaffinity list export LIST_ID --expand people \
  --expand-filter "status!=Inactive" \
  --all --csv output.csv

# Multiple conditions (AND logic)
xaffinity list export LIST_ID --expand people \
  --expand-filter "name=Alice,primaryEmail!=none" \
  --all --csv output.csv
```

Supported operators:
- `field=value` - exact match
- `field!=value` - not equal

Multiple conditions are separated by `,` or `;` and use AND logic.

## Error Handling

```bash
# Default: stop on first error
xaffinity list export LIST_ID --expand people --all --csv output.csv

# Continue on per-entry errors (skip failed entries)
xaffinity list export LIST_ID --expand people --expand-on-error skip --all --csv output.csv
```

Use `--expand-on-error skip` for permissive exports where partial data is acceptable.

## Important Constraints

1. **No cursor with expand:** `--cursor` cannot be combined with `--expand`. Use `--all` for complete exports.

2. **Memory considerations:** `--expand-all` with `--csv-mode nested` loads all associations into memory per entry. For entries with hundreds of associations, prefer `--csv-mode flat`.

3. **Truncation warnings:** When associations are truncated due to `--expand-max-results`, a warning is emitted at the end of the export.

4. **Opportunities expansion is expensive:** Without `--expand-opportunities-list`, expanding opportunities requires searching all opportunity lists, which can be very slow.

## Options Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--expand` | choice (repeatable) | - | Expand type: `people`, `companies`, or `opportunities` |
| `--expand-max-results` | int | 100 | Max associations per entry per type |
| `--expand-all` | flag | false | Fetch all associations (no limit) |
| `--expand-fields` | string (repeatable) | - | Specific fields to include |
| `--expand-field-type` | choice (repeatable) | - | Field types: `global`, `enriched`, `relationship-intelligence` |
| `--expand-on-error` | choice | `raise` | Error handling: `raise` or `skip` |
| `--csv-mode` | choice | `flat` | CSV format: `flat` or `nested` |
| `--expand-filter` | string | - | Filter associations (e.g., `field=value`) |
| `--expand-opportunities-list` | string | - | Scope `--expand opportunities` to a specific list |
