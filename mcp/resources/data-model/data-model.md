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
  opportunity get <id> --expand persons --expand companies
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

## Filtering List Entries

### --filter (Direct Field Filtering)
```bash
list export Dealflow --filter 'Status="New"'
```
- Filter by any field value directly
- Works for any criteria you specify
- Use when you know the field name and value

### --saved-view (Pre-Configured Views)
```bash
list export Dealflow --saved-view "Active Pipeline"
```
- Uses a named view pre-configured in Affinity UI
- More efficient (server-side filtering)
- Caveat: You cannot query what filters a saved view applies

### Decision Flow
1. Get workflow config: `xaffinity://workflow-config/{listId}` (returns status options + saved views in one call)
2. If a saved view name clearly matches your intent (e.g., "Due Diligence" for DD stage) → use it
3. If no matching saved view, or you need specific field filtering → use `--filter`
4. When in doubt, use `--filter` - it's explicit and predictable

### Common Mistake: Confusing Status Values with Saved View Names
```bash
# ✗ WRONG - "New" is a Status field value, not a saved view name
list export Dealflow --saved-view "New"

# ✓ CORRECT - Filter by the Status field
list export Dealflow --filter 'Status="New"'
```

---

## Efficient Patterns (One-Shot)

### Query list entries with filter
```bash
list export Dealflow --filter "Status=New"     # ✓ One call
```

### Get list entries with specific field values
By default, `list export` only returns basic columns (listEntryId, entityType, entityId, entityName).
**To get custom field values** like Owner, Team Member, Status, use `--field` for each field:
```bash
list export Dealflow --field "Team Member" --field "Owner" --filter 'Status="New"'
```

**Tip:** `--saved-view` can be combined with `--field` to get server-side filtering (from the saved view) with explicit field selection.

### Query tool field selection
When using the `query` tool with listEntries, custom field values are **auto-fetched** when referenced in `groupBy`, `aggregate`, or `where` clauses:
```json
{"from": "listEntries", "where": {"path": "listName", "op": "eq", "value": "Dealflow"}, "groupBy": "fields.Status", "aggregate": {"count": {"count": true}}}
```

To select all custom fields explicitly, use `fields.*` wildcard:
```json
{"from": "listEntries", "where": {"path": "listId", "op": "eq", "value": 12345}, "select": ["listEntryId", "entityName", "fields.*"]}
```

### Multi-select field filtering
Multi-select dropdown fields (like "Team Member") return arrays from the API. The query engine handles these automatically:
- `eq` with scalar: checks if value is IN the array (membership)
- `eq` with array: checks set equality (order-insensitive)
- `has_any`: checks if array contains any of the specified values
- `has_all`: checks if array contains all of the specified values

```json
// Find entries where Team Member includes "LB"
{"from": "listEntries", "where": {"and": [{"path": "listName", "op": "eq", "value": "Dealflow"}, {"path": "fields.Team Member", "op": "eq", "value": "LB"}]}}
```

### Get interactions for a company or person
```bash
interaction ls --type all --company-id 12345                                   # All interactions ever with company
interaction ls --type email --type meeting --company-id 12345 --days 90        # Emails and meetings, last 90 days
interaction ls --type meeting --company-id 12345 --days 90 --max-results 10    # Recent meetings with company
interaction ls --type email --person-id 67890 --max-results 5                  # Most recent emails with person
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

Or use the resource: `xaffinity://field-catalogs/{listId}` for field schema with descriptions.

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

**Symbolic Operators**:
- `=` equals
- `!=` not equals
- `=~` contains (case-insensitive)
- `=^` starts with (case-insensitive)
- `=$` ends with (case-insensitive)
- `>` `<` `>=` `<=` comparisons

**Word-based Operators** (SDK filter extension):
- `contains`, `starts_with`, `ends_with` - string matching
- `in [val1, val2]` - value in list
- `between [low, high]` - value in range
- `has_any [val1, val2]` - array contains any
- `has_all [val1, val2]` - array contains all
- `is null`, `is not null`, `is empty` - null/empty checks

**Examples**:
- `--filter 'name =~ "Acme"'`
- `--filter "Status=Active"`
- `--filter 'Industry = "Software"'`
- `--filter 'email =$ "@acme.com"'`
- `--filter 'Status in ["New", "Active"]'`

## Query vs Filter

- `--filter`: Structured filtering with operators (preferred)
- `--query`:  free-text search (simple text matching)

Use `--filter` for precise matching, `--query` for fuzzy text search.
