#!/usr/bin/env bash
# server.d/health-checks.sh - Verify external dependencies for xaffinity MCP Server
#
# These checks run at server startup to ensure required commands are available.
# If any check fails, the server will report an unhealthy status to the client.
#
# Note: JSON processing (jq/gojq) is handled by mcp-bash via MCPBASH_JSON_TOOL.
# If neither is available, mcp-bash enters minimal mode gracefully.

# Required: Affinity CLI for all API operations
mcp_health_check_command "xaffinity" "Affinity CLI (xaffinity)"

# Required: API key must be configured for API operations
# Check if xaffinity can validate the key (returns 0 if valid)
if ! xaffinity config check-key --json >/dev/null 2>&1; then
    mcp_log_warn "Affinity API key not configured or invalid"
    mcp_log_warn "Run 'xaffinity config setup-key' to configure"
fi

# Required: CLI commands registry for CLI Gateway tools
# Check bundled location first, then fallback to development location
if [[ -f "${MCPBASH_PROJECT_ROOT}/server.d/registry/commands.json" ]]; then
    REGISTRY_FILE="${MCPBASH_PROJECT_ROOT}/server.d/registry/commands.json"
else
    REGISTRY_FILE="${MCPBASH_PROJECT_ROOT}/.registry/commands.json"
fi
if [[ -f "$REGISTRY_FILE" ]]; then
    mcp_log_debug "CLI commands registry found: $REGISTRY_FILE"
else
    mcp_log_warn "CLI commands registry not found: $REGISTRY_FILE"
    mcp_log_warn "CLI Gateway tools (discover-commands, execute-*-command) will not work"
fi
