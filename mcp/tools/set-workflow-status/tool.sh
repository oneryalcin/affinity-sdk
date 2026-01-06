#!/usr/bin/env bash
# tools/set-workflow-status/tool.sh - Update status for a workflow item
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/field-resolution.sh"

# Extract arguments
list_id="$(mcp_args_require '.listId' 'listId is required')"
list_entry_id="$(mcp_args_require '.listEntryId' 'listEntryId is required')"
status="$(mcp_args_require '.status' 'status is required')"

# Get workflow config to find status field
config=$(get_or_fetch_workflow_config "$list_id")
status_field=$(echo "$config" | jq_tool -c '.statusField')

if [[ "$status_field" == "null" ]]; then
    mcp_fail -32602 "List does not have a status field configured"
fi

field_id=$(echo "$status_field" | jq_tool -r '.fieldId')

# Resolve status text to option ID if needed
if [[ "$status" =~ ^[0-9]+$ ]]; then
    # Already an ID
    status_option_id="$status"
else
    # Resolve text to ID
    status_option_id=$(resolve_status_option_id "$list_id" "$status") || {
        # Show available options
        options=$(echo "$status_field" | jq_tool -r '.options[].text' | tr '\n' ', ' | sed 's/,$//')
        mcp_fail_invalid_args "Unknown status: '$status'. Available: $options"
    }
fi

# Update the field value
result=$(run_xaffinity field-value set \
    --list-entry-id "$list_entry_id" \
    --field-id "$field_id" \
    --value "$status_option_id" \
    --output json --quiet \
    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} 2>&1) || {
    mcp_fail -32603 "Failed to update status: $result"
}

mcp_emit_json "$(jq -n \
    --argjson listId "$list_id" \
    --argjson listEntryId "$list_entry_id" \
    --arg status "$status" \
    --arg fieldId "$field_id" \
    '{
        success: true,
        listId: $listId,
        listEntryId: $listEntryId,
        status: $status,
        fieldId: $fieldId
    }'
)"
