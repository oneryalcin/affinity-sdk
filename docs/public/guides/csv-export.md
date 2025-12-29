# CSV Export Guide

This guide shows you how to export data from the Affinity CLI to CSV format for use in spreadsheets, data analysis tools, or other applications.

## Quick Start

Export data to CSV using the `--csv` flag:

```bash
# Export all people to CSV
affinity person ls --all --csv people.csv

# Export all companies to CSV
affinity company ls --all --csv companies.csv

# Export all opportunities to CSV
affinity opportunity ls --all --csv opportunities.csv

# Export list entries with custom fields
affinity list export 12345 --all --csv entries.csv
```

## Excel Compatibility

If you're opening CSV files in Microsoft Excel, use the `--csv-bom` flag to ensure proper character encoding:

```bash
affinity person ls --all --csv people.csv --csv-bom
```

This adds a UTF-8 Byte Order Mark (BOM) to the file, which helps Excel correctly display special characters, accents, and non-English text.

## Commands with Built-in CSV Support

| Command | CSV Flag | Example |
|---------|----------|---------|
| `person ls` | ✅ `--csv` | `affinity person ls --all --csv people.csv` |
| `company ls` | ✅ `--csv` | `affinity company ls --all --csv companies.csv` |
| `opportunity ls` | ✅ `--csv` | `affinity opportunity ls --all --csv opps.csv` |
| `list export` | ✅ `--csv` | `affinity list export 12345 --all --csv entries.csv` |

**Note:** The `--csv` flag requires `--all` to fetch all pages of data. Single-page exports are not supported for CSV output.

## CSV Column Reference

### person ls

The `person ls` command exports these columns:

- **id** - Person ID
- **name** - Full name (first + last)
- **primaryEmail** - Primary email address
- **emails** - All email addresses (semicolon-separated)

Example output:
```csv
id,name,primaryEmail,emails
123,Alice Smith,alice@example.com,alice@example.com
456,Bob Jones,bob@company.com,bob@company.com; bjones@company.com
```

### company ls

The `company ls` command exports these columns:

- **id** - Company ID
- **name** - Company name
- **domain** - Primary domain
- **domains** - All domains (semicolon-separated)

Example output:
```csv
id,name,domain,domains
100,Acme Corp,acme.com,acme.com
101,Beta Inc,beta.com,beta.com; beta.co
```

### opportunity ls

The `opportunity ls` command exports these columns:

- **id** - Opportunity ID
- **name** - Opportunity name
- **listId** - List ID the opportunity belongs to

Example output:
```csv
id,name,listId
10,Series A,41780
11,Seed Round,41780
```

### list export

The `list export` command is the most powerful CSV export option. It includes:

- Entity ID and name
- All custom field values
- List entry metadata

See `affinity list export --help` for details.

## Advanced: Using jq for Custom CSV Exports

For commands without built-in `--csv` support, you can use `jq` to convert JSON output to CSV format.

### Basic Pattern

```bash
affinity <command> --json --all | \
  jq -r '.data.<entity>[] | [.field1, .field2, .field3] | @csv' > output.csv
```

The `-r` flag is crucial - it outputs raw strings instead of JSON-quoted values.

### Examples

**Export field values:**
```bash
affinity field-value ls --field-id field-12345 --json | \
  jq -r '.data.fieldValues[] | [.fieldId, .value, .entityId] | @csv'
```

**Export notes:**
```bash
affinity note ls --person-id 123 --json --all | \
  jq -r '.data.notes[] | [.id, .content, .createdAt] | @csv'
```

**Export interactions:**
```bash
affinity interaction ls --person-id 123 --json --all | \
  jq -r '.data.interactions[] | [.id, .date, .type] | @csv'
```

**Add headers manually:**
```bash
affinity person ls --json --all | \
  jq -r '["ID","Name","Email"],
         (.data.persons[] | [.id, .name, .primaryEmail]) | @csv'
```

**Handle arrays (join with semicolons):**
```bash
affinity person ls --json --all | \
  jq -r '.data.persons[] | [.id, .name, (.emails | join("; "))] | @csv'
```

**Extract from nested structures:**
```bash
affinity person get 123 --json | \
  jq -r '.data.person.fields[] | [.fieldId, .value, .listEntryId] | @csv'
```

## JSON Data Structure Reference

All CLI commands return data in a consistent structure:

```json
{
  "data": {
    "<entity-plural>": [ ... ]
  }
}
```

Entity paths for jq:
- **persons**: `.data.persons[]`
- **companies**: `.data.companies[]`
- **opportunities**: `.data.opportunities[]`
- **fieldValues**: `.data.fieldValues[]`
- **fieldValueChanges**: `.data.fieldValueChanges[]`
- **notes**: `.data.notes[]`
- **interactions**: `.data.interactions[]`
- **tasks**: `.data.tasks[]`

## Troubleshooting

### Empty Output

Make sure you're accessing the correct JSON path:

```bash
# ❌ Wrong - missing .data
affinity person ls --json | jq '.persons'

# ✅ Correct
affinity person ls --json | jq '.data.persons'
```

### CSV shows JSON strings

Use the `-r` flag with jq:

```bash
# ❌ Wrong - produces "[1,\"Alice\"]"
affinity person ls --json | jq '.data.persons[] | [.id, .name] | @csv'

# ✅ Correct - produces "1,Alice"
affinity person ls --json | jq -r '.data.persons[] | [.id, .name] | @csv'
```

### Special characters broken in Excel

Use the `--csv-bom` flag:

```bash
affinity person ls --all --csv people.csv --csv-bom
```

### Empty CSV file has no headers

This is expected behavior when there are no results. The CLI cannot determine column names without data. If you need headers even for empty results, use `list export` which has a known schema.

## Tips and Best Practices

### 1. Use --all for complete exports

The `--csv` flag requires `--all` to fetch all pages:

```bash
# ✅ Correct
affinity person ls --all --csv people.csv

# ❌ Won't work
affinity person ls --csv people.csv
```

### 2. Combine with filters

**Filtering on custom fields (recommended):**

When filtering on custom fields, use `--filter` for server-side filtering. This is more efficient as Affinity filters the data before sending it:

```bash
# ✅ Efficient: Server-side filtering on custom field
affinity person ls --filter 'field("Department") = "Sales"' --all --csv sales-people.csv
```

You can also combine `--filter` with jq for additional client-side processing:

```bash
# Filter server-side, then process with jq
affinity person ls --filter 'field("Department") = "Sales"' --json --all | \
  jq -r '.data.persons[] | [.id, .name, .primaryEmail] | @csv'
```

**Filtering on built-in properties:**

Built-in properties like `type`, `firstName`, `primaryEmail`, etc. cannot be filtered using `--filter` (which only works with custom fields). Use jq for client-side filtering:

```bash
# ⚠️ Less efficient: Client-side filtering on built-in 'type' property
# (downloads all data, then filters locally)
affinity person ls --json --all | \
  jq -r '.data.persons[] | select(.type == "internal") | [.id, .name] | @csv'
```

**Combining both approaches:**

For complex scenarios, combine server-side custom field filtering with client-side built-in property filtering:

```bash
# Filter on custom field server-side, then filter on type client-side
affinity person ls --filter 'field("Department") = "Sales"' --json --all | \
  jq -r '.data.persons[] | select(.type == "internal") | [.id, .name] | @csv'
```

### 3. Save queries as scripts

Create reusable export scripts:

```bash
#!/bin/bash
# export-pipeline.sh

affinity person ls --all --csv people.csv --csv-bom
affinity company ls --all --csv companies.csv --csv-bom
affinity opportunity ls --all --csv opportunities.csv --csv-bom

echo "Export complete!"
```

### 4. Schedule regular exports

Use cron or task scheduler for automated exports:

```bash
# Daily export at 2 AM
0 2 * * * /path/to/export-pipeline.sh
```

### 5. Handle large datasets

For very large exports, monitor progress:

```bash
# The CLI will show API call counts for large exports
affinity list export 12345 --all --csv large-export.csv
```

## Getting Help

- Run `affinity <command> --help` to see all available options
- Check `affinity --version` to ensure you have the latest version
- Report issues at https://github.com/anthropics/affinity-api-x/issues

## Related Documentation

- [JSON Output Guide](./json-output.md) - Understanding JSON structure
- [List Export Guide](./list-export.md) - Advanced list export features
- [Field Values Guide](./field-values.md) - Working with custom fields
