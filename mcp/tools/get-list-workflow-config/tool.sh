#!/usr/bin/env bash
# tools/get-list-workflow-config/tool.sh - Get workflow configuration for a list
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

# Extract arguments - accept either listId or listName
list_id="$(mcp_args_get '.listId // null')"
list_name="$(mcp_args_get '.listName // null')"

# Resolve list
if [[ "$list_id" == "null" || -z "$list_id" ]]; then
    if [[ "$list_name" == "null" || -z "$list_name" ]]; then
        mcp_fail_invalid_args "Either listId or listName is required"
    fi
    list_id=$(resolve_list "$list_name") || mcp_fail_invalid_args "List not found: $list_name"
fi

# Get workflow config (uses caching internally)
config=$(get_or_fetch_workflow_config "$list_id")

mcp_emit_json "$config"
