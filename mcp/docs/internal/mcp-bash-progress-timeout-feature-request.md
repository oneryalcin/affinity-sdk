# Feature Request: Progress-Aware Timeout Extension for mcp-bash

## Summary

Request for mcp-bash to support progress-aware timeout extension, where the watchdog timer resets when progress notifications are emitted by tools.

## Problem Statement

The current mcp-bash timeout mechanism uses a simple countdown watchdog that kills tools after `timeoutSecs` regardless of whether the tool is making progress. This causes legitimate long-running operations to timeout even when they're actively working and reporting progress.

### Real-World Example

The xaffinity-mcp server's `list export` command with client-side filtering:

```bash
# This command needs to scan 9000+ rows to find matches
xaffinity list export Dealflow --filter "Status=New" --max-results 5
```

**What happens:**
1. Tool emits progress every ~0.65 seconds: `{"type":"progress","message":"Scanning 2100... (0 matches)"}`
2. After 30 seconds, watchdog kills the process (exit code 137)
3. MCP returns: `{"_mcpToolError":true,"code":-32603,"message":"Tool timed out"}`

**Evidence from testing:**
```json
{"_mcpToolError":true,"code":-32603,"message":"Tool timed out","data":{
  "exitCode": 137,
  "_meta": {
    "exitCode": 137,
    "stderr": "/Users/.../mcpbash/lib/timeout.sh: line 69: 75187 Killed: 9"
  }
}}
```

## Current Implementation Analysis

### timeout.sh Watchdog (lines 87-153)

```bash
mcp_timeout_spawn_watchdog() {
    # ...
    remaining="${seconds}"

    while [ "${remaining}" -gt 0 ]; do
        sleep 1
        if ! kill -0 "${worker_pid}" 2>/dev/null; then
            exit 0  # Process completed normally
        fi
        # Token check for cancellation, but NO progress check
        remaining=$((remaining - 1))
    done

    # Timeout reached - kill the process
    kill -TERM "${worker_pid}"
    # ...
}
```

The watchdog:
- Counts down from `seconds` to 0
- Checks if process is still alive
- Checks for cancellation token changes
- **Does NOT check for progress emission**

### Progress Emission Path

Progress flows through a separate path:
1. Tool calls `mcp_progress` which writes to `MCP_PROGRESS_STREAM`
2. Progress is forwarded to MCP client via `notifications/progress`
3. Watchdog is completely unaware of this activity

## Proposed Solution

### Option A: Progress File Monitor (Recommended)

Modify the watchdog to monitor a progress indicator file:

```bash
mcp_timeout_spawn_watchdog() {
    local worker_pid="$1"
    local seconds="$3"
    local progress_file="${MCPBASH_STATE_DIR}/progress.${worker_pid}"

    local last_progress_time=$(date +%s)

    while true; do
        sleep 1

        # Check if process completed
        if ! kill -0 "${worker_pid}" 2>/dev/null; then
            exit 0
        fi

        # Check for recent progress
        if [ -f "${progress_file}" ]; then
            local file_mtime=$(stat -f %m "${progress_file}" 2>/dev/null || stat -c %Y "${progress_file}" 2>/dev/null)
            if [ "${file_mtime}" -gt "${last_progress_time}" ]; then
                last_progress_time="${file_mtime}"
                # Progress received - continue without timeout
                continue
            fi
        fi

        # Check if idle too long (no progress within timeout period)
        local now=$(date +%s)
        if [ $((now - last_progress_time)) -ge "${seconds}" ]; then
            # Timeout - no progress for ${seconds}
            kill -TERM "${worker_pid}"
            break
        fi
    done
}
```

### Option B: Named Pipe/Signal Based

Use a named pipe or signal to communicate progress from the tool to the watchdog.

### Configuration

Add tool metadata option:
```json
{
  "timeoutSecs": 30,
  "progressExtendsTimeout": true
}
```

Or environment variable:
```bash
MCPBASH_PROGRESS_EXTENDS_TIMEOUT=true
```

## Evidence from Documentation

The mcp-bash BEST-PRACTICES.md already hints at progress keeping connections alive:

> **Line 1215**: "Prefer short defaults with retries over very long-running tools. If clients require streaming, **add progress signals every ~5 seconds to keep the channel alive**."

This suggests the intent exists but only for client-side keepalive, not server-side timeout extension.

## Impact

### Without This Feature

Tools that process large datasets must either:
1. Use very long static timeouts (wastes resources on stuck tools)
2. Artificially limit operations (poor UX for legitimate use cases)
3. Accept random timeouts on larger operations

### With This Feature

- Tools can have short default timeouts (30s)
- Progress emission keeps the operation alive
- Truly stuck tools (no progress) still timeout appropriately
- Better alignment with MCP protocol's progress notification intent

## Related Files in mcp-bash

- `lib/timeout.sh` - Watchdog implementation
- `lib/tools.sh:1753-1757` - Timeout wrapper invocation
- `lib/progress.sh` - Progress emission helpers
- `lib/core.sh:706+` - Worker environment setup

## Workarounds (Current)

1. **Increase static timeout** - Simple but resource-inefficient
2. **Limit operation scope** - Use `--max-results` to reduce scan time
3. **Split operations** - Multiple smaller calls instead of one large one

---

## Related Feature Request: Standard Debug File Detection

### Problem

Each mcp-bash project must implement its own debug file detection in `server.d/env.sh`:

```bash
_XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
_DEBUG_FILE="${_XDG_CONFIG_HOME}/<project-name>/debug"
if [[ -f "$_DEBUG_FILE" ]]; then
    export MCPBASH_LOG_LEVEL="debug"
fi
```

This is boilerplate that every project duplicates.

### Proposed Solution

mcp-bash should provide built-in debug file detection:

1. **Standard locations** (checked in order):
   - `MCPBASH_LOG_LEVEL=debug` environment variable
   - `~/.config/mcp-bash/<server-name>/debug` (XDG, server-specific)
   - `~/.config/mcp-bash/debug` (XDG, global for all servers)
   - `${MCPBASH_PROJECT_ROOT}/.debug` (local development)

2. **Server name from metadata**: Use `server.d/server.meta.json` `name` field

3. **Helper for projects**: Export `MCPBASH_CONFIG_HOME` for project-specific config

### Benefits

- Consistent debug experience across all mcp-bash servers
- No boilerplate in project's env.sh
- Users can enable debug globally or per-server
- mcpb bundles work out of the box

---

**Author**: Generated for xaffinity-mcp
**Date**: 2026-01-08
**mcp-bash version**: 0.9.4
