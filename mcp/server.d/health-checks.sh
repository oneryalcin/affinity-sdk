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
