# Affinity Data Model

> **MCP Note**: When using commands via MCP tools, output format (JSON) is handled automatically. Do not include `--json` in arguments.

> ⚠️ **Performance Warning**: Using `fields.*` (select all custom fields) on lists with 50+ fields can cause timeouts. **Always select specific fields** like `fields.Status`, `fields.Owner` instead.

**📖 Read Before Querying:**
- `xaffinity://query-guide` - **Read this first** for query performance tips, field selection best practices, and operator reference
- `xaffinity://workflows-guide` - **Read for complex tasks** covering common patterns, error handling, and when to use query vs CLI

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

### Checking List Membership

To check if a company/person is in a specific list, use `--expand list_entries`:

```bash
company get 12345 --expand list_entries
person get john@example.com --expand list_entries
```

Response includes all lists the entity belongs to:
```json
{
  "data": {
    "id": 12345,
    "name": "Acme Corp",
    "list_entries": [
      { "id": 99999, "list_id": 500, "list": { "id": 500, "name": "Dealflow" } },
      { "id": 99998, "list_id": 501, "list": { "id": 501, "name": "Portfolio" } }
    ]
  }
}
```

Check if `data.list_entries[].list.name` matches your target list (e.g., "Dealflow").

**Why this is efficient**: Fetches one entity's data instead of scanning an entire list. Use this for single lookups. For batch checks, use `query` with a `companyId IN [...]` filter.

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

**Best practice: Select only the fields you need:**
```json
{"from": "listEntries", "where": {"path": "listName", "op": "eq", "value": "Dealflow"}, "select": ["entityName", "fields.Status", "fields.Owner"]}
```

⚠️ **Avoid `fields.*` for lists with many custom fields** - it fetches ALL field values which can be slow (60+ seconds for lists with 50+ fields). Only use `fields.*` when you genuinely need every field.

### Query tool expand (interaction dates)
Use `expand: ["interactionDates"]` to add last/next meeting dates and email activity to each record:
```json
{"from": "listEntries", "where": {"path": "listName", "op": "eq", "value": "Dealflow"}, "expand": ["interactionDates"], "limit": 50}
```
Unlike `include` (which fetches related entities separately), `expand` merges computed data directly into each record.

### Expand/Include Practical Limits

Both `expand` and `include` trigger N+1 API calls (one per record). MCP tools support dynamic timeout extension for these operations, but there are practical limits:

| Records | Estimated Time | MCP Result |
|---------|----------------|------------|
| ≤100 | ~2 minutes | ✅ Completes normally |
| ~200 | ~5 minutes | ✅ Completes with progress |
| ~400 | ~9 minutes | ✅ Near ceiling |
| 430+ | 10+ minutes | ⚠️ May hit 10-minute ceiling |

**Recommendations:**
- For ≤100 records: Use freely
- For 100-400 records: Works but takes time; consider if you need all records
- For 400+ records: Batch into smaller queries or use CLI directly (not via MCP)

### Multi-select field filtering
Multi-select dropdown fields (like "Team Member") return arrays. Use `eq` for membership check, `has_any`/`has_all` for multiple values:
```json
{"from": "listEntries", "where": {"and": [{"path": "listName", "op": "eq", "value": "Dealflow"}, {"path": "fields.Team Member", "op": "eq", "value": "LB"}]}}
```
See `xaffinity://query-guide` for all multi-select operators.

### Get interactions for a company or person
```bash
interaction ls --type all --company-id 12345                                   # All interactions ever with company
interaction ls --type email --type meeting --company-id 12345 --days 90        # Emails and meetings, last 90 days
interaction ls --type meeting --company-id 12345 --days 90 --max-results 10    # Recent meetings with company
interaction ls --type email --person-id 67890 --max-results 5                  # Most recent emails with person
```

### Get interaction date summaries
For quick overview of last/next meetings and email activity without fetching full interaction history:
```bash
company get 12345 --with-interaction-dates                 # Last/next meeting dates, email dates
person get 67890 --with-interaction-dates                  # Same for persons
```

**For bulk interaction dates on list entries**, use the `query` tool with `expand: ["interactionDates"]`:
```json
{"from": "listEntries", "where": {"path": "listName", "op": "eq", "value": "Dealflow"}, "expand": ["interactionDates"], "limit": 50}
```
See "Expand/Include Practical Limits" section above for performance guidance.

The `--with-interaction-dates` flag returns:
- `lastMeeting.date`, `lastMeeting.daysSince`, `lastMeeting.teamMembers`
- `nextMeeting.date`, `nextMeeting.daysUntil`, `nextMeeting.teamMembers`
- `lastEmail.date`, `lastEmail.daysSince`
- `lastInteraction.date`, `lastInteraction.daysSince`

### Find unreplied messages
```bash
list export Dealflow --check-unreplied                     # Find unreplied incoming messages (email/chat)
list export Dealflow --check-unreplied --unreplied-types email  # Email only
list export Dealflow --check-unreplied --unreplied-lookback-days 60  # Custom lookback
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

### Audit field changes (who changed what, when)
```bash
field history field-123456 --person-id 789           # See change history for a field on a person
field history field-123456 --company-id 456          # Field history on a company
field history field-123456 --list-entry-id 999       # Field history on a list entry
```

Use `field history` to:
- Track who changed a deal's status and when
- Audit field value modifications over time
- Investigate when a field was last updated

**Note**: Requires the field ID (from `field ls`) and exactly one entity selector (`--person-id`, `--company-id`, `--opportunity-id`, or `--list-entry-id`).

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

### Mistake 3: Using JSON format for bulk queries

When using the `query` tool for bulk data retrieval, **always use TOON format** (the default):

```json
// ✗ WRONG - JSON format causes truncation on large result sets
{"format": "json", "query": {"from": "listEntries", "where": {...}}}

// ✓ RIGHT - Use TOON (or omit format to use default)
{"query": {"from": "listEntries", "where": {...}}}
{"format": "toon", "query": {"from": "listEntries", "where": {...}}}
```

**Why this matters:**
- JSON format causes truncation on result sets >15-20 records (wastes API calls)
- TOON is 40% more token-efficient and prevents truncation
- Only use `format: "json"` when you need to programmatically parse nested structures outside of Claude

## Full Scan Protection

The MCP gateway protects against expensive unbounded scans:

| Behavior | Details |
|----------|---------|
| Default limit | 1000 records (auto-injected) |
| Maximum limit | 10000 records (higher values capped) |
| `--all` flag | **Blocked** with error message |

**To fetch more than 10000 records:**
Use cursor pagination:
```bash
# First request
list export Dealflow --max-results 10000
# Returns: {"nextCursor": "abc123", ...}

# Subsequent requests
list export Dealflow --cursor abc123 --max-results 10000
```

**Why is `--all` blocked?**
Unbounded scans can consume your entire API quota and take hours.
Explicit limits force intentional decisions about data volume.

---

## Async Operations (Merges)

Some operations run asynchronously and return a **task URL** instead of completing immediately.

### Merge Operations (Beta)
Merge duplicate companies or persons into a primary record:
```bash
company merge 123 456    # Merge company 456 into company 123
person merge 789 101     # Merge person 101 into person 789
```

These return a `taskUrl` that you can poll for completion:
```json
{"survivingId": 123, "mergedId": 456, "taskUrl": "https://api.affinity.co/v2/tasks/..."}
```

### Waiting for Task Completion
```bash
task wait "https://api.affinity.co/v2/tasks/abc123"              # Wait up to 5 min (default)
task wait "https://api.affinity.co/v2/tasks/abc123" --timeout 60 # Wait up to 60 seconds
task get "https://api.affinity.co/v2/tasks/abc123"               # Check status without waiting
```

Task statuses: `pending`, `in_progress`, `success`, `failed`

---

## Reading Files

Files can be attached to companies, persons, and opportunities. To read file content:

### Step 1: List files to get file IDs
```bash
company files ls 306016520
person files ls 67890
opportunity files ls 98765
```

This returns file metadata including `id` in `data[].id`.

### Step 2: Get presigned URL
Use the `get-file-url` tool with the file ID:
```
get-file-url fileId=9192757
```

This returns a presigned URL valid for **60 seconds** that requires no authentication.

### Step 3: Fetch content
Use WebFetch immediately with the presigned URL to retrieve the file content.

### ⚠️ Claude Desktop Limitation

**WebFetch cannot access `userfiles.affinity.co`** due to Claude Desktop's domain sandbox. This limitation applies to ALL Claude Desktop users:

- Adding the domain to **Settings → Capabilities → Additional allowed domains** does NOT work
- Setting **Domain allowlist** to **"All domains"** does NOT work
- This is a known platform limitation (not an xaffinity issue)

**Related bug reports:**
- [#19087 - Additional allowed domains not applied](https://github.com/anthropics/claude-code/issues/19087)
- [#11897 - Domain allowlist issues](https://github.com/anthropics/claude-code/issues/11897)

**Workarounds:**
1. **Copy the URL** returned by `get-file-url` and open in a browser
2. Use CLI directly (not via MCP) with `files download --file-id`
3. **Coming soon**: `files read` command will return content inline, bypassing WebFetch entirely

### Why presigned URLs?
- Avoids base64 encoding overhead (33% larger)
- Content goes directly to Claude's multimodal processing
- Better for large files (PDFs, images)

### File size considerations
- Files up to 10MB can be fetched via presigned URL
- Larger files may need to be processed in chunks or downloaded locally

---

## Filter Syntax (V2 API)

CLI commands use `--filter 'field op "value"'` syntax:
```bash
--filter 'name =~ "Acme"'           # contains
--filter "Status=Active"            # equals
--filter 'email =$ "@acme.com"'     # ends with
--filter 'Status in ["New", "Active"]'  # in list
```

Common operators: `=` `!=` `=~` (contains) `=^` (starts) `=$` (ends) `>` `<` `>=` `<=`

For the `query` tool, use JSON operators (`eq`, `contains`, `in`, etc.) - see `xaffinity://query-guide` for complete reference.

## Query vs Filter

- `--filter`: Structured filtering with operators (preferred)
- `--query`: Free-text search (simple text matching)

Use `--filter` for precise matching, `--query` for fuzzy text search.

## Output Formats

### TOON (Token-Oriented Object Notation)

Some commands may output data in **TOON format** - a structured format specifically designed for LLM consumption with reduced token costs.

**Do NOT manually parse TOON output.** Use the official Python library:

```bash
pip install git+https://github.com/toon-format/toon-python.git
```

```python
from toon_format import decode

data = decode(toon_string)  # Returns proper Python dict/list
```

**For multi-step processing, save to file first** (don't embed TOON output inline in scripts):
```python
from toon_format import decode

# Save MCP tool result to file, then process
with open('/tmp/data.toon') as f:
    data = decode(f.read())
# Now iterate on analysis without re-querying
```

**Why this matters:**
- TOON looks like tabular/CSV data but has specific parsing rules
- Manual parsing with string splitting or regex is fragile and error-prone
- The `toon-format` library handles all edge cases correctly

**Reference:** https://github.com/toon-format/toon-python

---

## Handling Truncated Responses

Large query results may be truncated to fit within output limits (~50KB default). When this happens, the response includes a `nextCursor` field that allows you to fetch the remaining data.

### Detecting Truncation

Truncated responses include:
- `truncated: true` in the MCP response
- `nextCursor`: Opaque string to fetch the next chunk

### Resuming with Cursor

To get the next chunk of results, call the query tool again with:
1. The **exact same `query` object** (unchanged)
2. The **exact same `format` parameter** (unchanged)
3. The `cursor` parameter set to the `nextCursor` value

**Important**: Changing any query field or format invalidates the cursor.

### Example

```python
# First request
result1 = await query(
    query={"from": "persons", "limit": 1000},
    format="toon",
    maxOutputBytes=50000
)

# If truncated, get next chunk
if result1.get("truncated") and result1.get("nextCursor"):
    result2 = await query(
        query={"from": "persons", "limit": 1000},  # IDENTICAL query
        format="toon",  # IDENTICAL format
        cursor=result1["nextCursor"]  # Pass the cursor
    )
```

### Cursor Behavior

- Cursors are typically 150-500 bytes (base64-encoded)
- Cursors expire after 1 hour
- Cursors are mode-specific:
  - **Streaming mode** (simple queries): Fast resumption via API cursor
  - **Full-fetch mode** (queries with orderBy/aggregate): Cached results served from disk
- Pass the cursor back unchanged - it's opaque and should not be modified
