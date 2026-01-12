---
name: affinity-mcp-workflows
description: Use when working with Affinity CRM via MCP tools - find entities, manage workflows, log interactions, prepare briefings, find warm intros. Also use when user mentions "pipeline", "deals", "relationship strength", or wants to prepare for meetings.
---

# Affinity MCP Workflows

This skill covers the xaffinity MCP server tools, prompts, and resources for working with Affinity CRM.

## Prerequisites

The MCP server requires the xaffinity CLI to be installed:

```bash
pip install "affinity-sdk[cli]"
```

The CLI must be configured with an API key before the MCP server will work.

## IMPORTANT: Write Operations Only After Explicit User Request

**Only use tools or prompts that modify CRM data when the user explicitly asks to do so.**

Write operations include:
- **Tools**: `execute-write-command`
- **Prompts**: `log-interaction-and-update-workflow`, `change-status`, `log-call`, `log-message`

Read-only operations (search, lookup, briefings) can be used proactively to help the user. But never create, update, or delete CRM records unless the user specifically requests it.

## Available Tools

### CLI Gateway (Primary Interface)

The CLI Gateway provides full access to the xaffinity CLI:

| Tool | Use Case |
|------|----------|
| `discover-commands` | Search CLI commands by keyword (e.g., "create person", "export list") |
| `execute-read-command` | Execute read-only CLI commands (get, search, list, export) |
| `execute-write-command` | **(write)** Execute write CLI commands (create, update, delete) |

**Usage pattern:**

1. **Discover** the right command: `discover-commands(query: "create person", category: "write")`
2. **Execute** it: `execute-write-command(command: "person create", argv: ["--first-name", "John", "--last-name", "Doe"])`

### Utility Tools

| Tool | Use Case |
|------|----------|
| `get-entity-dossier` | Comprehensive entity info (details, relationship strength, interactions, notes, list memberships) |
| `read-xaffinity-resource` | Access dynamic resources via `xaffinity://` URIs |

### Destructive Commands

Commands that delete data require double confirmation:

1. **Look up the entity first** using `execute-read-command` to show what will be deleted
2. **Ask the user in your response** by showing them the entity details and requesting confirmation
3. **Wait for user's next message** - do NOT proceed until they explicitly confirm
4. **Only after user confirms** should you execute with `confirm: true`

Example flow:
```
User: "Delete person 123"
You: execute-read-command(command: "person get", argv: ["123"])
You: "This will permanently delete John Smith (ID: 123, email: john@example.com).
      Type 'yes' to confirm deletion."
[Stop here and wait for user's response]

User: "yes"
You: execute-write-command(command: "person delete", argv: ["123"], confirm: true)
```

## Common CLI Commands

Use `discover-commands` to find commands, then `execute-read-command` or `execute-write-command` to run them.

### Search & Lookup

| Command | Use Case |
|---------|----------|
| `person ls --query "..."` | Search persons by name/email |
| `company ls --filter 'name =~ "..."'` | Search companies |
| `list ls` | List all Affinity lists |
| `list export "<listName>"` | Export list entries (supports --filter) |
| `field ls --list-id <id>` | Get field definitions and dropdown options for a list |

### Entity Details

| Command | Use Case |
|---------|----------|
| `person get <id>` | Get person details |
| `company get <id>` | Get company details |
| `opportunity get <id>` | Get opportunity details |
| `relationship-strength ls --external-id <id>` | Get relationship strength for a person |
| `interaction ls --person-id <id> --type all` | Get all interactions (or use specific type: email, meeting, call, chat-message) |
| `field history <field-id> --person-id <id>` | View field value change history. **Requires exactly one entity selector**: `--person-id`, `--company-id`, `--opportunity-id`, or `--list-entry-id` |

### Write Operations

| Command | Use Case |
|---------|----------|
| `interaction create --type call --person-id <id>` | Log a call/meeting/email |
| `note create --person-id <id> --content "..."` | Add a note |
| `entry field "<list>" <entryId> --set <field> <value>` | Update a field value |
| `person create --first-name "..." --last-name "..."` | Create a person |

## MCP Prompts (Guided Workflows)

These prompts provide guided multi-step workflows. Suggest them when appropriate.

**Note**: Prompts marked with (write) modify CRM data - only use when user explicitly requests.

| Prompt | Type | When to Suggest |
|--------|------|-----------------|
| `prepare-briefing` | read-only | User has upcoming meeting, needs context on a person/company |
| `pipeline-review` | read-only | User wants weekly/monthly pipeline review |
| `warm-intro` | read-only | User wants to find introduction path to someone |
| `interaction-brief` | read-only | Get interaction history summary for an entity |
| `log-interaction-and-update-workflow` | **write** | User explicitly asks to log a call/meeting and update pipeline |
| `change-status` | **write** | User explicitly asks to move a deal to new stage |
| `log-call` | **write** | User explicitly asks to log a phone call |
| `log-message` | **write** | User explicitly asks to log a chat/text message |

### How to Invoke Prompts

Prompts are invoked with arguments. Example:
- `prepare-briefing(entityName: "John Smith", meetingType: "demo")`
- `warm-intro(targetName: "Jane Doe", context: "partnership discussion")`
- `log-interaction-and-update-workflow(personName: "Alice", interactionType: "call", summary: "Discussed pricing")`

## Resources

Access dynamic data via `xaffinity://` URIs using `read-xaffinity-resource`:

| URI | Returns |
|-----|---------|
| `xaffinity://me` | Current authenticated user details |
| `xaffinity://me/person-id` | Current user's person ID in Affinity |
| `xaffinity://interaction-enums` | Valid interaction types and directions |
| `xaffinity://saved-views/{listId}` | Saved views available for a list |
| `xaffinity://field-catalogs/{listId}` | Field definitions for a list |
| `xaffinity://workflow-config/{listId}` | Workflow configuration for a list |

## Common Workflow Patterns

### Before a Meeting
1. Use `get-entity-dossier` for full context (relationship strength, recent interactions, notes)
2. **Or use**: `prepare-briefing` prompt for a guided flow

### After a Call/Meeting
1. Use `execute-write-command` with `interaction create` to log what happened
2. Use `execute-read-command` with `list export` to find list entry (if updating pipeline)
3. Use `execute-write-command` with `entry field` if deal stage changed
4. **Or use**: `log-interaction-and-update-workflow` prompt

### Finding Warm Introductions
1. Use `execute-read-command` with `person ls` to locate target person
2. Use `execute-read-command` with `relationship-strength ls` for connection strength
3. **Or use**: `warm-intro` prompt for guided flow

### Pipeline Review
1. Use `execute-read-command` with `field ls --list-id` to see fields/statuses
2. Use `execute-read-command` with `list export` to see items
3. **Or use**: `pipeline-review` prompt

### Updating Deal Status
1. Use `execute-read-command` with `list export` to find the entry
2. Use `execute-read-command` with `field ls --list-id` to see available statuses
3. Use `execute-write-command` with `entry field` to update
4. **Or use**: `change-status` prompt

## Tips

- **Entity types**: `person`, `company`, `opportunity`
- **Interaction types**: `call`, `meeting`, `email`, `chat_message`, `in_person`
- **Dossier is comprehensive**: `get-entity-dossier` returns relationship strength, interactions, notes, and list memberships in one call
- **Use names directly**: Most commands accept names instead of IDs (e.g., `list export "Dealflow"`)
- **Filter syntax**: `--filter 'field op "value"'` (ops: `=`, `!=`, `=~` contains, `=^` starts with, `=$` ends with, `>`, `<`, `>=`, `<=`)
  - **Multi-word field names** MUST be quoted: `--filter '"Team Member"=~"LB"'`
  - **Multi-word values** MUST be quoted: `--filter 'Status="Intro Meeting"'`
  - **Both multi-word**: `--filter '"Referred By"="John Smith"'`
  - Single-word field/value can be unquoted: `--filter 'Status=New'`
  - Invalid (will fail): `--filter 'Team Member=LB'` (unquoted multi-word field name)
- **Filter only works on list fields**: The `--filter` option for `list export` filters on **list-defined fields** (Status, Owner, etc.), NOT internal properties like `entityId`, `entityType`, or `listEntryId`. Use `field ls --list-id <id>` to see available filter fields.
- **Finding a specific entity in a list**: To find a company/person in a list by their entity ID, either:
  1. Use `company get <id> --expand list-entries` to see their list memberships directly
  2. Or export the list and filter client-side (the tool will return `entityId` in results)
- **Output formats**: The `format` parameter controls result format:
  - `json` (default): Full structure with envelope, best for programmatic use
  - `markdown`: Best for LLM comprehension when analyzing data
  - `toon`: 30-60% fewer tokens, best for large datasets
  - `csv`: For spreadsheet export
  - Use `markdown` when you need to analyze/summarize results, `toon` for large exports

## Troubleshooting

If tools aren't working or returning unexpected results:

### Enable Debug Mode

```bash
# Enable (persistent, works with any MCP client)
mkdir -p ~/.config/xaffinity-mcp && touch ~/.config/xaffinity-mcp/debug

# Restart the MCP client (Claude Desktop: Cmd+Q, reopen)

# Disable when done
rm ~/.config/xaffinity-mcp/debug
```

### View Logs

**Claude Desktop**: `tail -f ~/Library/Logs/Claude/mcp-server-*.log`

Debug logs show component prefixes like `[xaffinity:tool:1.2.3]` to identify which component produced each message.

### Common Issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Tools show old behavior after update | Cached MCP server process | Fully quit and restart Claude Desktop |
| API key errors | Key not configured | Run `xaffinity config setup-key` |
| CLI version errors | Outdated CLI | Run `pip install --upgrade affinity-sdk`
