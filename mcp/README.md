# xaffinity MCP Server

An MCP (Model Context Protocol) server for Affinity CRM, built with the [MCP Bash Framework](https://github.com/yaniv-golan/mcp-bash-framework).

## Features

- **Entity Management** - Search and lookup persons, companies, and opportunities
- **Workflow Management** - View and update pipeline status, manage list entries
- **Relationship Intelligence** - Get relationship strength scores and find warm intro paths
- **Interaction Logging** - Log calls, meetings, emails, and messages
- **Session Caching** - Efficient caching to minimize API calls

## Installation

### Prerequisites

- Bash 3.2+
- jq 1.6+
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

```bash
MCPBASH_LOG_LEVEL=debug ./xaffinity-mcp.sh
```

## License

See the main repository license.
