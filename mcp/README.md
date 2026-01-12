# xaffinity MCP Server

An MCP (Model Context Protocol) server for Affinity CRM, built with the [MCP Bash Framework](https://github.com/yaniv-golan/mcp-bash-framework).

## Features

- **Entity Management** - Search and lookup persons, companies, and opportunities
- **Workflow Management** - View and update pipeline status, manage list entries
- **Relationship Intelligence** - Get relationship strength scores and find warm intro paths
- **Interaction Logging** - Log calls, meetings, emails, and messages
- **Session Caching** - Efficient caching to minimize API calls

## Quick Start

```bash
# 1. Install the xaffinity CLI
pip install affinity-sdk

# 2. Configure your API key
xaffinity config setup-key

# 3. Install the MCP server (choose one)
#    - Claude Desktop: Download and double-click xaffinity-mcp-*.mcpb
#    - Claude Code: /plugin marketplace add yaniv-golan/affinity-sdk
```

## Prerequisites

### For Claude Desktop / MCPB Installation (Recommended)

The `.mcpb` bundle is self-contained — it includes the MCP Bash Framework and gojq. You only need:

| Requirement | How to Install | Verify |
|-------------|----------------|--------|
| Python 3.9+ | [python.org](https://python.org) or your package manager | `python --version` |
| xaffinity CLI | `pip install affinity-sdk` | `xaffinity --version` |
| Affinity API key | `xaffinity config setup-key` | `xaffinity config check-key` |

### For Manual Installation

Manual installation requires additional dependencies:

| Requirement | How to Install | Verify |
|-------------|----------------|--------|
| Bash 3.2+ | Included on macOS/Linux; Windows: use WSL or Git Bash | `bash --version` |
| Python 3.9+ | [python.org](https://python.org) or your package manager | `python --version` |
| jq or gojq | See [Installing jq/gojq](#installing-jqgojq) below | `jq --version` or `gojq --version` |
| xaffinity CLI | `pip install affinity-sdk` | `xaffinity --version` |
| Affinity API key | `xaffinity config setup-key` | `xaffinity config check-key` |

#### Installing jq/gojq

Either [jq](https://jqlang.org/) or [gojq](https://github.com/itchyny/gojq) works — the server auto-detects which is available.

**Which to choose:**
- **jq** (recommended) — The original, widely available, full regex support
- **gojq** — Pure Go implementation, also supports YAML, better error messages

**Install jq:**

| Platform | Command |
|----------|---------|
| macOS | `brew install jq` |
| Debian/Ubuntu | `sudo apt-get install jq` |
| Fedora | `sudo dnf install jq` |
| Arch Linux | `sudo pacman -S jq` |
| Windows | `winget install jqlang.jq` or `choco install jq` |

**Install gojq (alternative):**

| Platform | Command |
|----------|---------|
| macOS | `brew install gojq` |
| Any (Go required) | `go install github.com/itchyny/gojq/cmd/gojq@latest` |
| Binary download | [GitHub Releases](https://github.com/itchyny/gojq/releases) |

## Installation

### Option 1: Claude Desktop (One-Click)

The `.mcpb` bundle is fully self-contained — it includes the MCP framework and JSON processor.

1. Install the xaffinity CLI: `pip install affinity-sdk`
2. Configure your API key: `xaffinity config setup-key`
3. Download `xaffinity-mcp-*.mcpb` from the [latest release](https://github.com/yaniv-golan/affinity-sdk/releases/latest)
4. Double-click the file or drag it into Claude Desktop

### Option 2: Claude Code

```bash
/plugin marketplace add yaniv-golan/affinity-sdk
/plugin install mcp@xaffinity
```

### Option 3: Manual Installation

For other MCP clients or development. Requires [additional prerequisites](#for-manual-installation).

1. Download `xaffinity-mcp-plugin.zip` from the [latest release](https://github.com/yaniv-golan/affinity-sdk/releases/latest)
2. Extract and configure your MCP client (see [Usage](#usage) below)
3. Install the MCP Bash Framework:
   ```bash
   ./xaffinity-mcp.sh install
   ```
4. Validate your configuration:
   ```bash
   ./xaffinity-mcp.sh validate
   ```

## Troubleshooting

If the MCP server fails to start, run diagnostics:

```bash
./xaffinity-mcp.sh doctor
```

Common issues:

| Error | Cause | Solution |
|-------|-------|----------|
| "Could not detect xaffinity CLI" | CLI not installed | `pip install affinity-sdk` |
| "CLI version X is too old" | Outdated CLI | `pip install --upgrade affinity-sdk` |
| "API key not configured" | Missing credentials | `xaffinity config setup-key` |
| "No JSON processor found" | jq/gojq not installed (manual install only) | See [Installing jq/gojq](#installing-jqgojq) |
| "Framework not found" | MCP Bash not installed (manual install only) | `./xaffinity-mcp.sh install` |

For detailed debugging, see [docs/DEBUGGING.md](docs/DEBUGGING.md).

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

### CLI Gateway (Primary Interface)

The CLI Gateway provides full access to the xaffinity CLI with minimal token overhead:

| Tool | Description |
|------|-------------|
| `discover-commands` | Search CLI commands by keyword (e.g., "create person", "delete note") |
| `execute-read-command` | Execute read-only CLI commands (get, search, list) |
| `execute-write-command` | Execute write CLI commands (create, update, delete) |

### Query Tool

| Tool | Description |
|------|-------------|
| `query` | Execute structured JSON queries with filters, joins, and aggregations |

For complex data analysis (filtering, grouping, aggregations), use the `query` tool instead of individual CLI commands. See the [Query Language Reference](https://yaniv-golan.github.io/affinity-sdk/latest/reference/query-language/) for full documentation.

### Utility Tools

| Tool | Description |
|------|-------------|
| `get-entity-dossier` | Get comprehensive info for an entity (aggregates 5+ CLI calls) |
| `read-xaffinity-resource` | Read static MCP resources (data-model, etc.) |

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

#### Output Formats

Control the format of command results for optimal token efficiency:

```json
{"command": "person ls", "format": "markdown"}
```

| Format | Token Efficiency | Best For |
|--------|-----------------|----------|
| `json` | Low | Programmatic use (default) |
| `markdown` | Medium-High | **LLM comprehension** - best for analysis tasks |
| `toon` | **High (~40% fewer)** | Large datasets, batch operations |
| `csv` | Medium | Spreadsheet export |
| `jsonl` | Medium | Streaming workflows |

**Recommendations:**
- Use `markdown` when you need to analyze or summarize data (LLMs read tables well)
- Use `toon` for large exports to minimize tokens (30-60% smaller than JSON)
- Use `json` when you need full structure with pagination/metadata

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

Enable debug logging for troubleshooting. Debug mode shows version info at startup and adds component prefixes to all log messages.

```bash
# Persistent debug mode (recommended - survives reinstalls)
mkdir -p ~/.config/xaffinity-mcp && touch ~/.config/xaffinity-mcp/debug

# Session-only via environment variable
XAFFINITY_MCP_DEBUG=1 ./xaffinity-mcp.sh

# Disable persistent debug mode
rm ~/.config/xaffinity-mcp/debug
```

When debug mode is enabled, logs show:
```
[xaffinity-mcp:1.2.3] Debug mode enabled
[xaffinity-mcp:1.2.3] Versions: mcp=1.2.3 cli=0.6.9 mcp-bash=v0.9.3
[xaffinity-mcp:1.2.3] Process: pid=12345 started=2026-01-06T10:30:00-08:00
```

#### Log Locations

| Context | Log Location |
|---------|--------------|
| Claude Desktop (macOS) | `~/Library/Logs/Claude/mcp-server-xaffinity MCP.log` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\Logs\mcp-server-xaffinity MCP.log` |
| CLI standalone | stderr (console) |

#### Advanced Debug Options

| Variable | Description |
|----------|-------------|
| `XAFFINITY_MCP_DEBUG=1` | Enable debug mode (cascades to all components) |
| `MCPBASH_LOG_VERBOSE=true` | Show paths in logs (exposes file paths) |
| `MCPBASH_TRACE_TOOLS=true` | Enable shell tracing (`set -x`) for tools |

See [docs/DEBUGGING.md](docs/DEBUGGING.md) for full debugging guide.

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
