# AI Integrations

Connect AI tools to Affinity CRM for intelligent workflows, meeting preparation, and pipeline management.

## Choose Your Integration

| Integration | Best For | What It Provides |
|-------------|----------|------------------|
| [**MCP Server**](../mcp/index.md) | Any MCP-compatible AI tool | Tools for search, workflows, relationship intelligence |
| [**Claude Code Plugins**](../guides/claude-code-plugins.md) | Claude Code users | Skills that teach Claude SDK/CLI best practices |

## MCP Server

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server connects desktop AI applications to Affinity:

- **Claude Desktop**, **ChatGPT Desktop**, **Cursor**, **Windsurf**, **VS Code + Copilot**, and more
- 17 tools for entity search, relationship insights, workflow management, interaction logging, and full CLI access
- 8 guided prompts for common workflows (meeting prep, pipeline review, warm intros)

[MCP Server documentation](../mcp/index.md){ .md-button }

## Claude Code Plugins & Skills

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugins provide **skills**—knowledge packages that teach Claude domain-specific patterns:

| Plugin | Skill | What Claude Learns |
|--------|-------|-------------------|
| `sdk@xaffinity` | affinity-python-sdk | Typed IDs, context managers, pagination, filtering gotchas |
| `cli@xaffinity` | xaffinity-cli-usage | `--readonly` default, `--json` output, API key verification |

[Claude Code Plugins documentation](../guides/claude-code-plugins.md){ .md-button }

## Quick Install

### MCP Server

**One-click install (recommended):**

Download the `.mcpb` bundle from [GitHub Releases](https://github.com/yaniv-golan/affinity-sdk/releases), then double-click or drag to Claude Desktop.

**Manual install:**

```bash
pip install "affinity-sdk[cli]"
xaffinity config setup-key
```

Then add to your MCP client's configuration:

```json
{
  "mcpServers": {
    "xaffinity": {
      "command": "/path/to/affinity-sdk/mcp/xaffinity-mcp.sh"
    }
  }
}
```

### Claude Code Plugins

```bash
/plugin marketplace add yaniv-golan/affinity-sdk
/plugin install sdk@xaffinity   # SDK patterns
/plugin install cli@xaffinity   # CLI patterns
/plugin install mcp@xaffinity   # MCP server (Claude Code only)
```

## When to Use What

| Scenario | Recommended |
|----------|-------------|
| Writing Python scripts with the SDK | SDK plugin (skills) |
| Running CLI commands | CLI plugin (skills) |
| Meeting prep, pipeline management, logging interactions | MCP Server |
| Using Claude Desktop, Cursor, or other MCP clients | MCP Server |
| Using Claude Code for development | Both plugins + optionally MCP |
