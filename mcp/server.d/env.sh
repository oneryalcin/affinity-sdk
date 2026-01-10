#!/usr/bin/env bash
# server.d/env.sh - Environment setup for xaffinity MCP Server
#
# ==============================================================================
# Tool Environment Passthrough
# ==============================================================================
# Allow policy environment variables to be passed through to tool scripts.
# By default, mcp-bash only passes MCP*/MCPBASH* variables for security.
# We use "allowlist" mode to also pass AFFINITY_MCP_* policy variables.
#
# Available policy variables:
#   AFFINITY_MCP_READ_ONLY=1         - Restrict to read-only operations
#   AFFINITY_MCP_DISABLE_DESTRUCTIVE=1 - Block destructive commands entirely
#
# Session cache variables (auto-configured below):
#   AFFINITY_SESSION_CACHE           - Cache directory for cross-command caching
#   AFFINITY_SESSION_CACHE_TTL       - Cache TTL in seconds (default: 600)

export MCPBASH_TOOL_ENV_MODE="allowlist"
export MCPBASH_TOOL_ENV_ALLOWLIST="AFFINITY_MCP_READ_ONLY,AFFINITY_MCP_DISABLE_DESTRUCTIVE,XAFFINITY_DEBUG,AFFINITY_TRACE,AFFINITY_SESSION_CACHE,AFFINITY_SESSION_CACHE_TTL"

# ==============================================================================
# Debug Mode Configuration
# ==============================================================================
# Enable debug logging by creating server.d/.debug file (mcp-bash 0.9.5+ native):
#
#   touch server.d/.debug   # Enable debug logging
#   rm server.d/.debug      # Disable debug logging
#
# Environment variable MCPBASH_LOG_LEVEL=debug takes precedence if set.
# See mcp-bash docs/DEBUGGING.md for details.
# ==============================================================================

# Create session cache on server startup
if [[ -z "${AFFINITY_SESSION_CACHE:-}" ]]; then
    export AFFINITY_SESSION_CACHE="${TMPDIR:-/tmp}/xaffinity-mcp-session-$$"
    mkdir -p "${AFFINITY_SESSION_CACHE}"
    chmod 700 "${AFFINITY_SESSION_CACHE}"
fi

# Default cache TTL (10 minutes for MCP context)
export AFFINITY_SESSION_CACHE_TTL="${AFFINITY_SESSION_CACHE_TTL:-600}"

# ==============================================================================
# Debug Mode Auto-Configuration
# ==============================================================================
# When MCPBASH_LOG_LEVEL=debug, automatically enable xaffinity debug features

if [[ "${MCPBASH_LOG_LEVEL:-info}" == "debug" ]]; then
    # Enable xaffinity-specific debug logging
    export XAFFINITY_DEBUG="${XAFFINITY_DEBUG:-true}"

    # Enable CLI command tracing
    export AFFINITY_TRACE="1"

    # Capture tool stderr for debugging (mcp-bash feature)
    export MCPBASH_TOOL_STDERR_CAPTURE="${MCPBASH_TOOL_STDERR_CAPTURE:-true}"

    # Increase stderr tail limit for more context in errors
    export MCPBASH_TOOL_STDERR_TAIL_LIMIT="${MCPBASH_TOOL_STDERR_TAIL_LIMIT:-8192}"

    # Log raw argument payloads for debugging parsing issues
    export MCPBASH_DEBUG_PAYLOADS="${MCPBASH_DEBUG_PAYLOADS:-1}"
fi

# ==============================================================================
# Debug Log Directory (optional)
# ==============================================================================
# If XAFFINITY_DEBUG_LOG_DIR is set, write debug logs to files for analysis

if [[ -n "${XAFFINITY_DEBUG_LOG_DIR:-}" ]]; then
    mkdir -p "${XAFFINITY_DEBUG_LOG_DIR}" 2>/dev/null || true
    export XAFFINITY_DEBUG_LOG_FILE="${XAFFINITY_DEBUG_LOG_DIR}/xaffinity-mcp-$(date +%Y%m%d-%H%M%S).log"
fi
