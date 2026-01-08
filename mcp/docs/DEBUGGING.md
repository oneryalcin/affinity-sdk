# Debugging xaffinity-mcp

This guide explains how to enable debug logging for the xaffinity MCP server.

## Quick Start

```bash
# Enable debug mode
mkdir -p ~/.config/xaffinity-mcp && touch ~/.config/xaffinity-mcp/debug

# Restart your MCP client (e.g., Claude Desktop)

# Disable debug mode
rm ~/.config/xaffinity-mcp/debug
```

## Debug Mode Options

Debug mode can be enabled via (checked in priority order):

| Priority | Method | Use Case |
|----------|--------|----------|
| 1 | `XAFFINITY_MCP_DEBUG=1` env var | Session-specific, explicit |
| 2 | `~/.config/xaffinity-mcp/debug` file | Persistent across reinstalls |
| 3 | `.debug` file in server directory | Development/local testing |

## What Debug Mode Does

When enabled, debug mode:

1. **Cascades to all components**:
   - Sets `MCPBASH_LOG_LEVEL=debug` (mcp-bash framework)
   - Sets `XAFFINITY_DEBUG=true` (xaffinity tools)

2. **Shows version banner at startup**:
   ```
   [xaffinity-mcp:1.2.3] Debug mode enabled
   [xaffinity-mcp:1.2.3] Versions: mcp=1.2.3 cli=0.6.9 mcp-bash=v1.0.0
   [xaffinity-mcp:1.2.3] Process: pid=12345 started=2026-01-06T10:30:00-08:00
   ```

3. **Adds component prefixes to all logs**:
   - `[xaffinity:tool:1.2.3]` - Tool execution
   - `[xaffinity:cli:1.2.3]` - CLI command calls
   - `[xaffinity:gateway:1.2.3]` - CLI Gateway operations

## Log Locations

Debug output goes to different locations depending on how the MCP server is running:

| Context | Log Location |
|---------|--------------|
| Claude Desktop (macOS) | `~/Library/Logs/Claude/mcp-server-xaffinity MCP.log` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\Logs\mcp-server-xaffinity MCP.log` |
| Other MCP clients | Check client documentation |
| CLI standalone | stderr (console) |
| mcp-bash debug | `/tmp/mcpbash.debug.*/` |

**Note**: The log filename uses the server's display name from mcpb (`xaffinity MCP`), not the internal name.

### Viewing Claude Desktop Logs

```bash
# Find all xaffinity MCP logs
ls -la ~/Library/Logs/Claude/mcp-server-xaffinity*.log

# Follow logs in real-time
tail -f ~/Library/Logs/Claude/mcp-server-xaffinity\ MCP.log

# Search for errors (escape the space in filename)
grep -i "error\|timeout\|failed" ~/Library/Logs/Claude/mcp-server-xaffinity\ MCP.log

# Filter by component
grep "xaffinity:cli" ~/Library/Logs/Claude/mcp-server-xaffinity\ MCP.log

# Recent tool calls and errors
tail -200 ~/Library/Logs/Claude/mcp-server-xaffinity\ MCP.log | grep "tools/call\|error"
```

### What's Logged (Even Without Debug Mode)

Claude Desktop logs all JSON-RPC messages, so you can always see:
- Tool call requests (`tools/call`)
- Success/error responses
- Timeout errors (exit code 137 = SIGKILL from watchdog)
- CLI errors (exit code 2 = CLI validation/execution error)

## Troubleshooting

### Debug mode not working?

1. **Check if debug file exists**:
   ```bash
   [[ -f ~/.config/xaffinity-mcp/debug ]] && echo "Debug ON" || echo "Debug OFF"
   ```

2. **Restart the MCP client** - Changes require restart

3. **Check for stale processes**:
   ```bash
   ps aux | grep mcp-bash
   ```
   Kill old processes if needed.

### Version mismatch in logs?

If logs show an old version, the MCP client may have cached an old server process. Fully quit and restart the client.

### No logs appearing?

- Debug logs only appear in MCP server mode (connected to a client)
- `mcp-bash run-tool` doesn't produce MCP log output (no `MCP_LOG_STREAM`)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `XAFFINITY_MCP_DEBUG=1` | Enable debug mode |
| `XAFFINITY_MCP_VERSION` | Cached MCP server version (set at startup) |
| `MCPBASH_LOG_LEVEL` | mcp-bash log level (set to `debug` when debug enabled) |
| `MCPBASH_FRAMEWORK_VERSION` | mcp-bash framework version (set by framework at startup) |
| `XAFFINITY_DEBUG` | xaffinity tools debug flag (set to `true` when debug enabled) |

## mcp-bash Framework Debug Features

The mcp-bash framework (v0.9.3+) provides additional debug capabilities:

### Client Identity Logging

When debug mode is enabled, mcp-bash logs the connecting client at initialize:

```
[mcp.lifecycle] Client: claude-ai/0.1.0 pid=12345
```

This helps identify which mcp-bash process serves which client when multiple instances are running.

### Framework Version

The framework version is available via `MCPBASH_FRAMEWORK_VERSION` environment variable after initialization.
