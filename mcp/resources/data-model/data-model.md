# Affinity Data Model

## Core Concepts

### Companies and Persons (Global Entities)
**Companies** and **Persons** exist globally in your CRM, independent of any list.

- **Commands**: `company ls`, `person ls`, `company get`, `person get`
- **Filters**: Core fields (name, domain, email)
- **Use case**: Search or retrieve ANY company/person in your CRM
- Can be added to multiple lists

### Opportunities (List-Scoped Entities)
**Opportunities** are special - they ONLY exist within a specific list (a pipeline).

- **Commands**: `opportunity ls`, `opportunity get`
- Each opportunity belongs to exactly ONE list
- Opportunities have **associations** to Persons and Companies
- **Important**: V2 API returns partial data. To get associations:
  ```
  opportunity get <id> --expand people --expand companies
  ```

### Lists (Collections with Custom Fields)
**Lists** are pipelines/collections that organize entities.

- List types: Person lists, Company lists, Opportunity lists
- Each list has **custom Fields** (columns) defined by your team
- **Commands**: `list ls` (find lists), `list get` (list details)
- **Use case**: Find which lists exist and what fields they have

### List Entries (Entity + List Membership)
When an entity is added to a list, it becomes a **List Entry** with field values.

- Entries have **Field Values** specific to that list's custom fields
- **Commands**: `list export` (get entries), `list-entry get` (single entry)
- **Filters**: Based on list-specific field values (Status, Stage, etc.)
- **Use case**: Get entities from a specific list, filtered by list fields
- **Note**: Companies/Persons can be on multiple lists; Opportunities are on exactly one

## Selectors: Names Work Directly

Most commands accept **names, IDs, or emails** as selectors - no need to look up IDs first.

```bash
# These all work - use names directly!
list export Dealflow --filter "Status=New"     # list name
list export 41780 --filter "Status=New"        # list ID (also works)
company get "Acme Corp"                        # company name
person get john@example.com                    # email address
opportunity get "Big Deal Q1"                  # opportunity name
```

## Performance: Saved Views vs --filter

### Saved Views (Server-Side) - PREFERRED
```bash
list export Dealflow --saved-view "Active Deals"   # ✓ Server filters, returns only matches
```
- Uses pre-defined filters stored in Affinity
- Fast: API returns only matching entries
- Check available views first: read `xaffinity://saved-views/{listId}` resource

### --filter (Client-Side) - LAST RESORT
```bash
list export Dealflow --filter "Status=New"         # ✗ Downloads ALL, filters locally
```
- Downloads entire list, then filters in CLI
- Slow on large lists (1000+ entries)
- Use ONLY when no Saved View matches your criteria

**Decision flow**: Saved View exists? → Use `--saved-view`. No match? → Use `--filter`.

---

## Efficient Patterns (One-Shot)

### Query list entries with filter
```bash
list export Dealflow --filter "Status=New"     # ✓ One call
```

### Search companies globally
```bash
company ls --filter 'name =~ "Acme"'           # ✓ One call
```

### Get entity details
```bash
company get "Acme Corp"                        # ✓ One call (name works)
person get john@example.com                    # ✓ One call (email works)
```

### See list fields and dropdown options
```bash
field ls --list-id Dealflow                    # Returns all fields with dropdown options
```
The response includes `dropdownOptions` array for dropdown/ranked-dropdown fields with `id`, `text`, `rank`, `color`.

## Common Mistakes

### Mistake 1: Looking up IDs unnecessarily
```bash
# ✗ WRONG - unnecessary steps
list ls                                        # Step 1: find ID
list export 41780 --filter "Status=New"        # Step 2: use ID

# ✓ RIGHT - use name directly
list export Dealflow --filter "Status=New"     # One step!
```

### Mistake 2: Using wrong command for list fields
```bash
# ✗ WRONG - Status is a LIST field, not a company field
company ls --filter "Status=New"

# ✓ RIGHT - use list export for list-specific fields
list export Dealflow --filter "Status=New"
```

## Filter Syntax (V2 API)

All commands use the same filter syntax:
```
--filter 'field op "value"'
```

**Operators**:
- `=` equals
- `!=` not equals
- `=~` contains
- `=^` starts with
- `=$` ends with
- `>` `<` `>=` `<=` comparisons

**Examples**:
- `--filter 'name =~ "Acme"'`
- `--filter "Status=Active"`
- `--filter 'Industry = "Software"'`

## Query vs Filter

- `--filter`: Structured V2 API filtering with operators (preferred)
- `--query`: V1 API free-text search (simple text matching)

Use `--filter` for precise matching, `--query` for fuzzy text search.
