# xaffinity MCP Server

An MCP (Model Context Protocol) server for Affinity CRM, built with the [MCP Bash Framework](https://github.com/yaniv-golan/mcp-bash-framework).

## Features

- **Entity Management** - Search and lookup persons, companies, and opportunities
- **Workflow Management** - View and update pipeline status, manage list entries
- **Relationship Intelligence** - Get relationship strength scores and find warm intro paths
- **Interaction Logging** - Log calls, meetings, emails, and messages
- **Session Caching** - Efficient caching to minimize API calls

## Installation

### Option 1: Claude Desktop (One-Click)

1. Download `xaffinity-mcp-*.mcpb` from the [latest release](https://github.com/yaniv-golan/affinity-sdk/releases/latest)
2. Double-click the file or drag it into Claude Desktop
3. Configure your Affinity API key when prompted

### Option 2: Claude Code

```bash
/plugin marketplace add yaniv-golan/affinity-sdk
/plugin install mcp@xaffinity
```

### Option 3: Manual Installation

Download `xaffinity-mcp-plugin.zip` from the [latest release](https://github.com/yaniv-golan/affinity-sdk/releases/latest) and configure your MCP client manually (see [Usage](#usage) below).

### Prerequisites

- Bash 3.2+
- jq 1.6+ or gojq (auto-detected via `MCPBASH_JSON_TOOL`)
- xaffinity CLI (`pip install affinity-python-sdk`)
- Configured Affinity API key (`xaffinity config setup-key`)

### Install Framework

```bash
./xaffinity-mcp.sh install
```

### Validate Configuration

```bash
./xaffinity-mcp.sh validate
```

## Usage

### With Claude Code

The server is automatically available through the Claude plugin at `.claude-plugin/mcp.json`.

### With Other MCP Clients

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "xaffinity": {
      "command": "/path/to/affinity-sdk/mcp/xaffinity-mcp.sh"
    }
  }
}
```

## Tools

### Specialized Tools (14)

| Tool | Description |
|------|-------------|
| `find-entities` | Search for persons, companies, or opportunities |
| `find-lists` | Search for Affinity lists |
| `get-list-workflow-config` | Get workflow configuration for a list |
| `get-workflow-view` | Get items from a workflow view |
| `resolve-workflow-item` | Resolve entity to list entry ID |
| `set-workflow-status` | Update status for a workflow item |
| `update-workflow-fields` | Update multiple fields on a workflow item |
| `get-entity-dossier` | Get comprehensive info for an entity |
| `add-note` | Add a note to an entity |
| `get-relationship-insights` | Get relationship insights and intro paths |
| `get-status-timeline` | Get status change history |
| `log-interaction` | Log an interaction (call, meeting, etc.) |
| `get-interactions` | Get interactions for an entity |
| `read-xaffinity-resource` | Read static MCP resources |

### CLI Gateway Tools (3)

These tools provide full access to the xaffinity CLI with minimal token overhead:

| Tool | Description |
|------|-------------|
| `discover-commands` | Search CLI commands by keyword (e.g., "create person", "delete note") |
| `execute-read-command` | Execute read-only CLI commands (get, search, list) |
| `execute-write-command` | Execute write CLI commands (create, update, delete) |

#### CLI Gateway Usage

1. **Discover** the right command:
   ```json
   {"query": "add person to list", "category": "write"}
   ```
   Returns compact text format:
   ```
   # cmd|cat|params (s=str i=int b=bool f=flag !=req *=multi)
   list entry add|w|LIST:s! --person-id:i --company-id:i
   ```

2. **Execute** the command:
   ```json
   {"command": "list entry add", "argv": ["Pipeline", "--person-id", "123"]}
   ```

#### Destructive Commands

Commands that delete data require explicit confirmation:
```json
{"command": "person delete", "argv": ["456"], "confirm": true}
```

The `confirm: true` parameter is required for destructive commands. The tool will automatically append `--yes` to bypass CLI prompts.

## Prompts

| Prompt | Description |
|--------|-------------|
| `prepare-briefing` | Prepare for a meeting with comprehensive context |
| `log-interaction-and-update-workflow` | Log interaction and update pipeline |
| `pipeline-review` | Review a workflow pipeline |
| `change-status` | Change workflow status with documentation |
| `warm-intro` | Find warm introduction paths |
| `log-call` | Quick log a phone call |
| `log-message` | Quick log a chat/text message |
| `interaction-brief` | Get interaction history summary |

## Configuration

### Read-Only Mode

Set `AFFINITY_MCP_READ_ONLY=1` to restrict to read-only tools:

```bash
AFFINITY_MCP_READ_ONLY=1 ./xaffinity-mcp.sh
```

### Disable Destructive Commands

Set `AFFINITY_MCP_DISABLE_DESTRUCTIVE=1` to block delete operations via CLI Gateway:

```bash
AFFINITY_MCP_DISABLE_DESTRUCTIVE=1 ./xaffinity-mcp.sh
```

This blocks `execute-write-command` from running any destructive commands (those marked `destructive: true` in the registry).

### Cache TTL

Adjust cache duration (default 10 minutes):

```bash
AFFINITY_SESSION_CACHE_TTL=300 ./xaffinity-mcp.sh
```

## Development

### Run Diagnostics

```bash
./xaffinity-mcp.sh doctor
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

#### Debug Environment Variables

| Variable | Description |
|----------|-------------|
| `MCPBASH_LOG_LEVEL=debug` | Enable mcp-bash framework debug logging |
| `XAFFINITY_DEBUG=true` | Enable xaffinity-specific debug logging |
| `MCPBASH_LOG_VERBOSE=true` | Show paths in logs (exposes file paths) |
| `MCPBASH_TRACE_TOOLS=true` | Enable shell tracing (`set -x`) for tools |

When `MCPBASH_LOG_LEVEL=debug` is set, the server automatically:
- Enables `XAFFINITY_DEBUG=true`
- Captures tool stderr (`MCPBASH_TOOL_STDERR_CAPTURE=true`)
- Increases stderr tail limit to 8KB for more error context

### Claude Code Plugin

The MCP server is also available as a Claude Code plugin, distributed via the repository's own marketplace (`.claude-plugin/marketplace.json`). For standalone MCP server usage with other clients, see the main [MCP documentation](https://yaniv-golan.github.io/affinity-sdk/latest/mcp/).

The plugin files must be assembled before publishing:

#### Build the plugin

```bash
make plugin
```

This copies the MCP server files into `.claude-plugin/`:
- `xaffinity-mcp.sh`, `xaffinity-mcp-env.sh`
- `tools/`, `prompts/`, `resources/`, `lib/`
- `completions/`, `providers/`, `scripts/`, `server.d/`

#### Clean build artifacts

```bash
make clean
```

#### Plugin structure

```
.claude-plugin/
├── plugin.json          # Plugin manifest (checked in)
├── skills/              # Claude Code skills (checked in)
├── xaffinity-mcp.sh     # MCP server (copied by make)
├── tools/               # MCP tools (copied by make)
├── prompts/             # MCP prompts (copied by make)
└── ...                  # Other MCP files (copied by make)
```

See [CONTRIBUTING.md](../CONTRIBUTING.md#mcp-plugin-development) for release instructions.

## License

See the main repository license.
