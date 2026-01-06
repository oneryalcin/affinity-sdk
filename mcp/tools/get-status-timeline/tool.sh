#!/usr/bin/env bash
# tools/get-status-timeline/tool.sh - Get status change history for a list entry
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

# Extract arguments
list_id="$(mcp_args_require '.listId' 'listId is required')"
list_entry_id="$(mcp_args_require '.listEntryId' 'listEntryId is required')"
limit="$(mcp_args_int '.limit' --default 20 --min 1 --max 100)"

cli_args=(--output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Get workflow config for status field info
config=$(get_or_fetch_workflow_config "$list_id")
status_field=$(echo "$config" | jq_tool -c '.statusField')
status_field_id="null"
if [[ "$status_field" != "null" ]]; then
    status_field_id=$(echo "$status_field" | jq_tool -r '.fieldId')
fi

# Get field value changes for this entry
# Filter to status field if we know it
changes=$(run_xaffinity_readonly field-value-change ls \
    --list-entry-id "$list_entry_id" \
    --max-results "$limit" \
    "${cli_args[@]}" 2>/dev/null | jq_tool -c '.data.fieldValueChanges // []' || echo "[]")

# Filter to status field changes if we have a status field
if [[ "$status_field_id" != "null" ]]; then
    status_changes=$(echo "$changes" | jq_tool -c --arg fid "$status_field_id" \
        '[.[] | select(.fieldId == ($fid | tonumber))]')
else
    # Return all field changes if no status field
    status_changes="$changes"
fi

# Transform to timeline format
timeline=$(echo "$status_changes" | jq_tool -c 'map({
    timestamp: .createdAt,
    fieldId: .fieldId,
    fieldName: .fieldName,
    actionType: .actionType,
    oldValue: .oldValue,
    newValue: .newValue,
    changedBy: .changedBy
})')

count=$(echo "$timeline" | jq_tool 'length')

mcp_emit_json "$(jq_tool -n \
    --argjson listId "$list_id" \
    --argjson listEntryId "$list_entry_id" \
    --argjson timeline "$timeline" \
    --argjson count "$count" \
    --argjson statusField "$status_field" \
    '{
        listId: $listId,
        listEntryId: $listEntryId,
        statusField: $statusField,
        timeline: $timeline,
        count: $count
    }'
)"
