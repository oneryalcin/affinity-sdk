# MCP Debugging Improvements Plan

## Status: Phase 1 Implemented
**Created**: 2026-01-06
**Updated**: 2026-01-06 (Phase 1 complete, pending Claude Desktop verification)
**Author**: Claude (with Yaniv)

---

## Problem Statement

Debugging issues between the MCP server, CLI, and mcp-bash framework is currently difficult due to:

1. **Multiple debug flags**: Different environment variables for each layer
2. **No version visibility**: Logs don't indicate which version of each component produced them
3. **Scattered log locations**: Logs end up in different places depending on context
4. **Hard to enable debugging**: Requires editing installed bundle files or rebuilding

### Evidence

From debugging session on 2026-01-06:

1. **Version confusion**: The installed bundle showed `version: 1.2.2` in manifest.json, but the actual code running was from a cached process started before the update:
   ```
   # Log showed old behavior despite "new" bundle
   "list":{"listId":41780,"name":"Unknown","type":"unknown"}
   ```

2. **Multiple processes**: `ps aux | grep mcp-bash` showed 100+ processes, making it unclear which was serving Claude Desktop

3. **Log location discovery**: Had to search multiple locations:
   - `~/Library/Logs/Claude/mcp-server-*.log` (Claude Desktop)
   - `~/Library/Logs/xaffinity/` (CLI)
   - `/tmp/mcpbash.debug.*/` (mcp-bash debug mode)

4. **No single debug switch**: Currently need to set:
   - `MCPBASH_LOG_LEVEL=debug` (mcp-bash framework)
   - `XAFFINITY_DEBUG=true` (xaffinity MCP tools)
   - CLI has separate `--verbose` flag

---

## Design Goals

### DX (Developer Experience)
- Single command/flag to enable full debugging
- Version info always visible in debug logs
- Clear component prefixes in all log messages
- Easy to toggle without rebuilding bundles

### UX (User Experience)
- Debug off by default (no noise, no performance impact)
- No extra log files cluttering disk
- Easy instructions when debugging is needed

---

## Proposed Solution

### 1. Single Debug Flag

**Flag**: `XAFFINITY_MCP_DEBUG=1`

When set, this cascades to enable debugging across all layers:

```bash
# In lib/common.sh or run-server.sh
if [[ "${XAFFINITY_MCP_DEBUG:-}" == "1" ]]; then
    export MCPBASH_LOG_LEVEL="debug"
    export XAFFINITY_DEBUG="true"
    # Future: export XAFFINITY_CLI_VERBOSE="true"
fi
```

**Rationale**: One flag to remember, one flag to document, one flag to set.

### 2. Version Banner at Startup

When debug mode is enabled, log version information:

```
[xaffinity-mcp:1.2.2] Debug mode enabled
[xaffinity-mcp:1.2.2] Component versions:
  - mcp-server: 1.2.2 (from VERSION file)
  - mcp-bash: 1.0.0 (from framework)
  - cli: 0.6.9 (from xaffinity --version)
[xaffinity-mcp:1.2.2] Process: pid=12345 started=2026-01-06T03:16:00Z
```

**Implementation**: Add to `run-server.sh` or a new `lib/debug.sh`:

```bash
# Cache version at startup (not on every log call - performance)
_xaffinity_cache_versions() {
    export XAFFINITY_MCP_VERSION=$(cat "${MCPBASH_PROJECT_ROOT}/VERSION" 2>/dev/null || echo "unknown")
    export XAFFINITY_MCPBASH_VERSION="${MCPBASH_VERSION:-unknown}"
    # CLI version fetched lazily only if debug banner requested (avoids subprocess on every startup)
}

xaffinity_debug_banner() {
    if [[ "${XAFFINITY_MCP_DEBUG:-}" != "1" ]]; then
        return
    fi

    # Lazy fetch CLI version only when actually logging banner
    local cli_version
    cli_version=$(xaffinity --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")

    mcp_log_info "xaffinity-mcp:$XAFFINITY_MCP_VERSION" "Debug mode enabled"
    mcp_log_info "xaffinity-mcp:$XAFFINITY_MCP_VERSION" "Versions: mcp=$XAFFINITY_MCP_VERSION cli=$cli_version mcp-bash=$XAFFINITY_MCPBASH_VERSION"
    mcp_log_info "xaffinity-mcp:$XAFFINITY_MCP_VERSION" "Process: pid=$$ started=$(date -Iseconds)"
}
```

**Performance note**: VERSION is cached at startup, not read on every log call. CLI version is fetched lazily only when debug banner is actually requested.

**Rationale**: When debugging, the first question is always "what version am I running?" - make this obvious.

### 3. Component Prefixes in Logs

Update logging functions to include component and version:

| Component | Prefix Format | Example |
|-----------|---------------|---------|
| mcp-bash framework | `[mcp-bash]` | `[mcp-bash] Tool invoke: find-lists` |
| xaffinity MCP tools | `[xaffinity:tool]` | `[xaffinity:tool] Executing get-workflow-view` |
| xaffinity CLI calls | `[xaffinity:cli]` | `[xaffinity:cli] Running: list export 41780` |
| CLI Gateway | `[xaffinity:gateway]` | `[xaffinity:gateway] Validated command: list ls` |

**Implementation**: Update `xaffinity_log_*` functions in `lib/common.sh`:

```bash
xaffinity_log_debug() {
    local context="$1"
    local message="$2"
    # Use cached version (set at startup by _xaffinity_cache_versions)
    local version="${XAFFINITY_MCP_VERSION:-?}"

    if [[ "${XAFFINITY_MCP_DEBUG:-}" == "1" ]]; then
        if type mcp_log_debug &>/dev/null; then
            mcp_log_debug "xaffinity:$context:$version" "$message"
        fi
    fi
}
```

**Performance note**: Uses cached `XAFFINITY_MCP_VERSION` - no file read per log call.

**Rationale**: When reading logs, immediately know which component produced each line.

### 4. Easy Debug Toggle Without Rebuild

Add `.debug` file support:

```bash
# In run-server.sh, before sourcing anything
DEBUG_FLAG_FILE="${MCPBASH_PROJECT_ROOT}/.debug"
if [[ -f "$DEBUG_FLAG_FILE" ]]; then
    export XAFFINITY_MCP_DEBUG=1
fi
```

**User workflow**:
```bash
# Enable debugging for installed bundle
touch "/Users/yaniv/Library/Application Support/Claude/Claude Extensions/local.mcpb.yaniv-golan.xaffinity-mcp/server/.debug"

# Restart Claude Desktop

# View logs
tail -f "/Users/yaniv/Library/Logs/Claude/mcp-server-Affinity CRM MCP Server.log"

# Disable debugging
rm "/Users/yaniv/Library/Application Support/Claude/Claude Extensions/local.mcpb.yaniv-golan.xaffinity-mcp/server/.debug"
```

**Rationale**: No need to edit JSON files, no need to rebuild bundles, just touch/rm a file.

### 5. Debug Log Location Documentation

Rather than duplicating logs with `tee` (which can cause file descriptor issues), simply document where logs appear:

**Claude Desktop**: `~/Library/Logs/Claude/mcp-server-Affinity CRM MCP Server.log`
**CLI standalone**: stderr (console)
**mcp-bash debug**: `/tmp/mcpbash.debug.*/` when `MCPBASH_LOG_LEVEL=debug`

The version banner (Section 2) ensures you can identify which component produced each log line.

**Rationale**: Keep it simple - don't add complexity, just document what already exists.

### 6. Helper Script for Debug Toggle

Provide a helper to manage the `.debug` file:

```bash
# In lib/debug-helper.sh (or documented command)
xaffinity_mcp_debug_path() {
    local installed_path="$HOME/Library/Application Support/Claude/Claude Extensions/local.mcpb.yaniv-golan.xaffinity-mcp/server/.debug"
    echo "$installed_path"
}

# User can then:
# touch "$(xaffinity_mcp_debug_path)"   # Enable
# rm "$(xaffinity_mcp_debug_path)"      # Disable
```

For now, document this path in `docs/DEBUGGING.md` rather than shipping a helper script.

### 7. Security Note

The `.debug` file approach is safe because:
- It only enables verbose logging (no code execution)
- The file is in a protected location (Application Support requires user access)
- Debug output goes to existing log files (no new attack surface)
- No secrets are logged (API keys are in environment, not logged)

---

## Enhancement Requests for mcp-bash

### Request 1: Version Export

**Current**: mcp-bash version not easily accessible from tools
**Requested**: Export `MCPBASH_VERSION` environment variable

```bash
# In mcp-bash startup
export MCPBASH_VERSION="1.0.0"  # Read from framework VERSION file
```

**Benefit**: Tools can log framework version without file reads.

### Request 2: Debug Mode Cascade

**Current**: `MCPBASH_LOG_LEVEL=debug` only affects mcp-bash logging
**Requested**: When debug, also export a flag tools can check:

```bash
# When MCPBASH_LOG_LEVEL=debug
export MCPBASH_DEBUG=1
```

**Benefit**: Tools don't need to parse log level strings.

### Request 3: Startup Banner Hook

**Current**: No hook for tools to log at server startup
**Requested**: Call a `server.d/on-startup.sh` if present

```bash
# mcp-bash calls this after initialization
if [[ -f "$MCPBASH_SERVER_DIR/on-startup.sh" ]]; then
    source "$MCPBASH_SERVER_DIR/on-startup.sh"
fi
```

**Benefit**: Clean place for version banner and debug initialization.

### Request 4: Process Identity Logging

**Current**: Hard to identify which mcp-bash process serves which client
**Requested**: Log client identity at connection:

```
[mcp-bash] Client connected: claude-ai/0.1.0 pid=12345
```

**Benefit**: When multiple processes running, know which is which.

---

## Implementation Plan

### Phase 1: Core Debug Flag (This PR)

1. Add `XAFFINITY_MCP_DEBUG` cascade in `lib/common.sh`
2. Add `.debug` file check in `run-server.sh`
3. Add version banner function
4. Update logging functions with component prefixes

**Files modified** (completed):
- `xaffinity-mcp.sh` - Added .debug file check, debug cascade, version caching, debug banner
- `lib/common.sh` - Added debug cascade (for run-tool mode), version caching, updated logging functions with version prefixes
- `.gitignore` - Added .debug to ignored files

**Note**: `run-server.sh` doesn't exist; the entry point is `xaffinity-mcp.sh`.

### Phase 2: Documentation

1. Create `docs/DEBUGGING.md` with user-facing instructions
2. Add troubleshooting section to skill

**Files to create**:
- `docs/DEBUGGING.md`

**Estimated effort**: 30 minutes

### Phase 3: mcp-bash Enhancements (Separate)

File enhancement requests with mcp-bash project:
- [ ] MCPBASH_VERSION export
- [ ] MCPBASH_DEBUG flag
- [ ] on-startup.sh hook
- [ ] Client identity logging

---

## Testing Plan

### Important: run-tool vs Server Mode

`mcp-bash run-tool` is for local testing and **does not set up `MCP_LOG_STREAM`**.
This means `mcp_log_*` calls are silently skipped in run-tool mode.

The full debug logging (version banner, component prefixes) only works when:
1. Running as an MCP server (Claude Desktop)
2. `MCP_LOG_STREAM` is connected to the MCP protocol

### Manual Testing

1. **Debug off (default)**:
   ```bash
   mcp-bash run-tool find-lists --args '{"query": "test"}'
   # Verify: No debug output, tool works normally
   ```

2. **Debug via .debug file**:
   ```bash
   touch .debug
   mcp-bash run-tool find-lists --args '{"query": "test"}'
   rm .debug
   # Verify: XAFFINITY_MCP_DEBUG=1 is set (visible if tool outputs env)
   # Note: mcp_log_* output won't appear (no MCP_LOG_STREAM in run-tool mode)
   ```

3. **Claude Desktop integration** (primary test):
   - Build and install bundle: `mcp-bash bundle && mcpb install dist/*.mcpb`
   - Touch .debug file in installed location:
     ```bash
     touch "/Users/yaniv/Library/Application Support/Claude/Claude Extensions/local.mcpb.yaniv-golan.xaffinity-mcp/server/.debug"
     ```
   - Restart Claude Desktop (Cmd+Q, reopen)
   - Use any tool via Claude
   - Check logs:
     ```bash
     tail -f "/Users/yaniv/Library/Logs/Claude/mcp-server-Affinity CRM MCP Server.log"
     ```
   - **Verify**: Version banner appears, logs have `[xaffinity:*:1.2.2]` prefix

---

## Open Questions

1. **Log rotation**: Should debug logs rotate automatically? Current approach appends indefinitely.

2. **Performance**: Is checking for `.debug` file on every tool invocation too slow? (Probably negligible)

3. **CLI integration**: Should `XAFFINITY_MCP_DEBUG` also enable CLI verbose mode? Need to check if CLI respects env vars.

4. **Structured logs**: Should debug logs be JSON for easier parsing? Or keep human-readable?

---

## References

- mcp-bash DEBUGGING.md: `/Users/yaniv/Documents/code/mcpbash/docs/DEBUGGING.md`
- Claude Desktop log location: `~/Library/Logs/Claude/mcp-server-*.log`
- Current xaffinity logging: `mcp/lib/common.sh` lines 38-91
