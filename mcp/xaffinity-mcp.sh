#!/usr/bin/env bash
# xaffinity-mcp.sh - Main launcher for xaffinity MCP Server
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MCPBASH_PROJECT_ROOT="${SCRIPT_DIR}"

# Framework version (pinned)
FRAMEWORK_VERSION="${MCPBASH_VERSION:-v0.8.3}"

# Framework location precedence:
# 1. Vendored: ${SCRIPT_DIR}/mcp-bash-framework/bin/mcp-bash
# 2. MCPBASH_HOME env override
# 3. XDG default: ${XDG_DATA_HOME:-$HOME/.local/share}/mcp-bash
# 4. Fallback: ${HOME}/.local/bin/mcp-bash

find_framework() {
    if [[ -x "${SCRIPT_DIR}/mcp-bash-framework/bin/mcp-bash" ]]; then
        echo "${SCRIPT_DIR}/mcp-bash-framework/bin/mcp-bash"
    elif [[ -n "${MCPBASH_HOME:-}" && -x "${MCPBASH_HOME}/bin/mcp-bash" ]]; then
        echo "${MCPBASH_HOME}/bin/mcp-bash"
    elif [[ -x "${XDG_DATA_HOME:-$HOME/.local/share}/mcp-bash/bin/mcp-bash" ]]; then
        echo "${XDG_DATA_HOME:-$HOME/.local/share}/mcp-bash/bin/mcp-bash"
    elif [[ -x "${HOME}/.local/bin/mcp-bash" ]]; then
        echo "${HOME}/.local/bin/mcp-bash"
    fi
}

# Handle special commands
case "${1:-}" in
    install)
        # Install framework and create PATH launcher
        "${SCRIPT_DIR}/scripts/install-framework.sh" "${FRAMEWORK_VERSION}"
        exit $?
        ;;
    doctor)
        # Run diagnostics (pass --fix to auto-repair)
        shift
        FRAMEWORK=$(find_framework)
        if [[ -n "$FRAMEWORK" ]]; then
            exec "$FRAMEWORK" doctor "$@"
        else
            echo "Framework not installed. Run: $0 install" >&2
            exit 1
        fi
        ;;
    validate)
        # Validate server configuration
        shift
        FRAMEWORK=$(find_framework)
        exec "$FRAMEWORK" validate --project-root "${SCRIPT_DIR}" "$@"
        ;;
esac

# Check API key configuration using xaffinity config check-key
# This detects keychain, dotenv, or env var configuration and returns the CLI pattern to use
check_key_output=$(xaffinity config check-key --json 2>/dev/null) || {
    echo "Error: Affinity API key not configured." >&2
    echo "" >&2
    echo "Run this command to set up your API key:" >&2
    echo "  xaffinity config setup-key" >&2
    echo "" >&2
    echo "Get your API key from: Affinity → Settings → API → Generate New Key" >&2
    exit 1
}

# Parse check-key output
configured=$(echo "$check_key_output" | jq -r '.configured // false')
if [[ "$configured" != "true" ]]; then
    echo "Error: Affinity API key not configured." >&2
    echo "" >&2
    echo "Run this command to set up your API key:" >&2
    echo "  xaffinity config setup-key" >&2
    echo "" >&2
    echo "Get your API key from: Affinity → Settings → API → Generate New Key" >&2
    exit 1
fi

# Extract the CLI pattern from check-key output
# Example patterns:
#   "xaffinity --dotenv --readonly <command> --json"  (dotenv mode)
#   "xaffinity --readonly <command> --json"           (keychain mode)
# Export for tool scripts to use when invoking xaffinity
export XAFFINITY_CLI_PATTERN=$(echo "$check_key_output" | jq -r '.pattern')

# Find and run framework
FRAMEWORK=$(find_framework)
if [[ -z "$FRAMEWORK" ]]; then
    echo "MCP Bash Framework not found. Run: $0 install" >&2
    exit 1
fi

# Tool allowlist (read-only vs full access)
AFFINITY_MCP_TOOLS_READONLY="find-entities find-lists get-list-workflow-config get-workflow-view resolve-workflow-item get-entity-dossier get-relationship-insights get-status-timeline get-interactions"
AFFINITY_MCP_TOOLS_ALL="${AFFINITY_MCP_TOOLS_READONLY} set-workflow-status update-workflow-fields add-note log-interaction"

if [[ "${AFFINITY_MCP_READ_ONLY:-}" == "1" ]]; then
    export MCPBASH_TOOL_ALLOWLIST="${AFFINITY_MCP_TOOLS_READONLY}"
else
    export MCPBASH_TOOL_ALLOWLIST="${AFFINITY_MCP_TOOLS_ALL}"
fi

exec "$FRAMEWORK" --project-root "${SCRIPT_DIR}" "$@"
