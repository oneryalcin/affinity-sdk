# MCP Server

The xaffinity MCP server connects desktop AI tools to Affinity CRM.

## Compatible Clients

MCP (Model Context Protocol) is an open standard. This server works with:

- **Claude Desktop** (Anthropic)
- **ChatGPT Desktop** (OpenAI)
- **Cursor** (AI IDE)
- **Windsurf** (AI IDE)
- **Zed** (AI-native editor)
- **VS Code + GitHub Copilot**
- **Continue** (open-source AI assistant)
- **JetBrains IDEs** (via MCP support)
- Any desktop application supporting [MCP stdio transport](https://modelcontextprotocol.io/)

## Features

- **Entity Search** - Find persons, companies, opportunities
- **Query Language** - Complex queries with filtering, includes, and aggregations
- **Relationship Intelligence** - Strength scores, warm intro paths
- **Workflow Management** - Update pipeline status, manage list entries
- **Interaction Logging** - Log calls, meetings, emails
- **Meeting Prep** - Comprehensive briefings before meetings

---

## Installation Options

### Option 1: MCPB Bundle (Recommended)

Download the `.mcpb` bundle for one-click installation:

1. Download `xaffinity-mcp-X.Y.Z.mcpb` from [GitHub Releases](https://github.com/yaniv-golan/affinity-sdk/releases)
2. Double-click the file or drag it to Claude Desktop
3. Configure your API key when prompted

MCPB bundles work with Claude Desktop and other MCPB-compatible clients.

### Option 2: Manual Configuration

For clients that don't support MCPB, configure manually:

**Prerequisites:**

1. Install the CLI:

```bash
pip install "affinity-sdk[cli]"
```

2. Configure your API key:

```bash
xaffinity config setup-key
```

3. Verify configuration:

```bash
xaffinity config check-key
```

---

## Client Configuration

For manual installation, add the MCP server to your client's configuration.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "xaffinity": {
      "command": "/path/to/affinity-sdk/mcp/xaffinity-mcp.sh"
    }
  }
}
```

### Cursor / Windsurf

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "xaffinity": {
      "command": "/path/to/affinity-sdk/mcp/xaffinity-mcp.sh"
    }
  }
}
```

### VS Code + GitHub Copilot

Add to your MCP settings:

```json
{
  "mcpServers": {
    "xaffinity": {
      "command": "/path/to/affinity-sdk/mcp/xaffinity-mcp.sh"
    }
  }
}
```

### Generic MCP Client

Any MCP client supporting stdio transport can connect using:

```json
{
  "mcpServers": {
    "xaffinity": {
      "command": "/path/to/affinity-sdk/mcp/xaffinity-mcp.sh"
    }
  }
}
```

Replace `/path/to/affinity-sdk` with your actual installation path.

---

## Available Tools (17)

### Search & Lookup (read-only)

| Tool | Description |
|------|-------------|
| `find-entities` | Search persons, companies, opportunities by name/email |
| `find-lists` | Find Affinity lists by name |
| `get-entity-dossier` | Comprehensive entity info: details, relationship strength, interactions, notes, list memberships |
| `read-xaffinity-resource` | Access dynamic resources via `xaffinity://` URIs |

### Workflow Management

| Tool | Description |
|------|-------------|
| `get-list-workflow-config` | Get workflow config (statuses, fields) for a list |
| `get-workflow-view` | Get items from a saved workflow view |
| `resolve-workflow-item` | Resolve entity to list entry ID (needed before status updates) |
| `set-workflow-status` | Update workflow item status **(write)** |
| `update-workflow-fields` | Update multiple fields on workflow item **(write)** |

### Relationships & Intelligence

| Tool | Description |
|------|-------------|
| `get-relationship-insights` | Relationship strength scores, warm intro paths via shared connections |
| `get-status-timeline` | Status change history for a workflow item |
| `get-interactions` | Interaction history (calls, meetings, emails) for an entity |

### Logging (write operations)

| Tool | Description |
|------|-------------|
| `add-note` | Add note to a person, company, or opportunity **(write)** |
| `log-interaction` | Log call, meeting, email, or chat message **(write)** |

### CLI Gateway (full CLI access)

These tools provide access to the full xaffinity CLI with minimal token overhead:

| Tool | Description |
|------|-------------|
| `discover-commands` | Search CLI commands by keyword (e.g., "create person", "delete note") |
| `execute-read-command` | Execute read-only CLI commands (get, search, list) |
| `execute-write-command` | Execute write CLI commands (create, update, delete) |

**Usage pattern:**

1. **Discover** the right command:
   ```json
   {"query": "add person to list", "category": "write"}
   ```

2. **Execute** the command:
   ```json
   {"command": "list entry add", "argv": ["Pipeline", "--person-id", "123"]}
   ```

**Destructive commands** (delete operations) require explicit confirmation:
```json
{"command": "person delete", "argv": ["456"], "confirm": true}
```

---

## Guided Workflows (8 Prompts)

MCP prompts provide guided multi-step workflows.

### Read-Only Prompts

| Prompt | Use Case |
|--------|----------|
| `prepare-briefing` | Before a meeting - get full context on a person/company |
| `pipeline-review` | Weekly/monthly pipeline review |
| `warm-intro` | Find introduction paths to someone |
| `interaction-brief` | Get interaction history summary for an entity |

### Write Prompts

| Prompt | Use Case |
|--------|----------|
| `log-interaction-and-update-workflow` | After a call/meeting - log and update pipeline |
| `change-status` | Move a deal to a new stage |
| `log-call` | Quick phone call logging |
| `log-message` | Quick chat/text message logging |

### Prompt Invocation

Prompts accept arguments:

```
prepare-briefing(entityName: "John Smith", meetingType: "demo")
warm-intro(targetName: "Jane Doe", context: "partnership discussion")
log-interaction-and-update-workflow(personName: "Alice", interactionType: "call", summary: "Discussed pricing")
```

---

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

---

## Common Workflow Patterns

### Before a Meeting

1. `find-entities` to locate the person/company
2. `get-entity-dossier` for full context (relationship strength, recent interactions, notes)
3. **Or use**: `prepare-briefing` prompt for a guided flow

### After a Call/Meeting

1. `log-interaction` to record what happened
2. `resolve-workflow-item` to get list entry ID (if updating pipeline)
3. `set-workflow-status` if deal stage changed
4. **Or use**: `log-interaction-and-update-workflow` prompt

### Finding Warm Introductions

1. `find-entities` to locate target person
2. `get-relationship-insights` for connection paths
3. **Or use**: `warm-intro` prompt for guided flow

### Pipeline Review

1. `find-lists` to locate the pipeline list
2. `get-workflow-view` to see items in a saved view
3. **Or use**: `pipeline-review` prompt

### Updating Deal Status

1. `find-entities` to find the opportunity
2. `resolve-workflow-item` to get list entry ID
3. `get-list-workflow-config` to see available statuses
4. `set-workflow-status` to update
5. **Or use**: `change-status` prompt

---

## Configuration

### Read-Only Mode

Restrict to read-only tools:

```bash
AFFINITY_MCP_READ_ONLY=1 ./xaffinity-mcp.sh
```

### Disable Destructive Commands

Allow write operations but block delete commands via CLI Gateway:

```bash
AFFINITY_MCP_DISABLE_DESTRUCTIVE=1 ./xaffinity-mcp.sh
```

### Cache TTL

Adjust cache duration (default 10 minutes):

```bash
AFFINITY_SESSION_CACHE_TTL=300 ./xaffinity-mcp.sh
```

### Debug Mode

Enable comprehensive logging for troubleshooting:

```bash
# Full debug mode - enables all debug features
MCPBASH_LOG_LEVEL=debug ./xaffinity-mcp.sh

# Test a single tool with debug output
MCPBASH_LOG_LEVEL=debug mcp-bash run-tool find-entities --args '{"query":"acme"}' --verbose

# Enable shell tracing for deep debugging
MCPBASH_TRACE_TOOLS=true mcp-bash run-tool get-entity-dossier --args '{"entityType":"person","entityId":"12345"}'
```

| Variable | Description |
|----------|-------------|
| `MCPBASH_LOG_LEVEL=debug` | Enable mcp-bash framework debug logging |
| `XAFFINITY_DEBUG=true` | Enable xaffinity-specific debug logging |
| `MCPBASH_LOG_VERBOSE=true` | Show paths in logs (exposes file paths) |
| `MCPBASH_TRACE_TOOLS=true` | Enable shell tracing (`set -x`) for tools |

### Diagnostics

Run health check:

```bash
./xaffinity-mcp.sh doctor
```

---

## Tips

- **Entity types**: `person`, `company`, `opportunity`
- **Interaction types**: `call`, `meeting`, `email`, `chat_message`, `in_person`
- **Dossier is comprehensive**: `get-entity-dossier` returns relationship strength, interactions, notes, and list memberships in one call
- **Resolve before update**: Always use `resolve-workflow-item` before `set-workflow-status` or `update-workflow-fields`
- **Check workflow config**: Use `get-list-workflow-config` to discover valid status options before updating

---

## Claude Code Installation

Using Claude Code? You can also install via the plugin marketplace:

```bash
/plugin marketplace add yaniv-golan/affinity-sdk
/plugin install mcp@xaffinity
```

This installs the MCP server automatically. See [Claude Code plugins](../guides/claude-code-plugins.md) for additional Claude-specific features.

---

## Discoverability

### MCPB Distribution

This server is distributed as an [MCPB bundle](https://github.com/modelcontextprotocol/mcpb) for one-click installation. Download from [GitHub Releases](https://github.com/yaniv-golan/affinity-sdk/releases).

### MCP Registry (Planned)

We plan to register this server with the [MCP Registry](https://registry.modelcontextprotocol.io/)—the official catalog for MCP servers.

### Future: .well-known Discovery

The MCP protocol is adding standardized discovery via `/.well-known/mcp.json` endpoints ([SEP-1649](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1649)). This will allow clients to auto-discover server capabilities without connecting first.
