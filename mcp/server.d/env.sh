#!/usr/bin/env bash
# server.d/env.sh - Environment setup for xaffinity MCP Server

# Create session cache on server startup
if [[ -z "${AFFINITY_SESSION_CACHE:-}" ]]; then
    export AFFINITY_SESSION_CACHE="${TMPDIR:-/tmp}/xaffinity-mcp-session-$$"
    mkdir -p "${AFFINITY_SESSION_CACHE}"
    chmod 700 "${AFFINITY_SESSION_CACHE}"
fi

# Default cache TTL (10 minutes for MCP context)
export AFFINITY_SESSION_CACHE_TTL="${AFFINITY_SESSION_CACHE_TTL:-600}"

# Enable tracing in debug mode
if [[ "${MCPBASH_LOG_LEVEL:-info}" == "debug" ]]; then
    export AFFINITY_TRACE="1"
fi
